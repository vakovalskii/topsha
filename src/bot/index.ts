/**
 * Telegram Bot - interface to ReAct Agent
 * Features: per-user workspace, traces, exec approvals (non-blocking)
 */

import { Telegraf, Context } from 'telegraf';
import { mkdirSync, existsSync } from 'fs';
import { join } from 'path';
import OpenAI from 'openai';
import { ReActAgent } from '../agent/react.js';
import { 
  toolNames, 
  setApprovalCallback, 
  setAskCallback, 
  setSendFileCallback, 
  setSendDmCallback,
  setDeleteMessageCallback, 
  setEditMessageCallback, 
  recordBotMessage, 
  setSendMessageCallback, 
  startScheduler,
  logGlobal, 
  shouldTroll, 
  getTrollMessage, 
  saveChatMessage, 
  setProxyUrl 
} from '../tools/index.js';
import { startProcessManager, markUserActive as markProcessUserActive } from '../tools/processManager.js';
import { startSandboxManager, shutdownSandbox } from '../tools/dockerSandbox.js';

// Import bot modules
import type { BotConfig, PendingQuestion } from './types.js';
import { 
  safeSend, 
  withUserLock, 
  setMaxConcurrentUsers, 
  canAcceptUser, 
  markUserActive, 
  markUserInactive 
} from './rate-limiter.js';
import { detectPromptInjection } from './security.js';
import { escapeHtml, mdToHtml, splitMessage } from './formatters.js';
import { 
  initReactionLLM, 
  shouldReact, 
  getSmartReaction 
} from './reactions.js';
import { 
  toolEmoji, 
  getToolComment, 
  toolTrackers, 
  TOOL_UPDATE_INTERVAL, 
  MIN_EDIT_INTERVAL_MS 
} from './tools-ui.js';
import { 
  setMainGroupChatId, 
  startAutonomousMessages,
  setOpenAIClient,
} from './thoughts.js';
import { 
  setupAllHandlers, 
  pendingQuestions 
} from './handlers.js';
import { CONFIG, getRandomDoneEmoji } from '../config.js';
import { 
  setupAllCommands, 
  isAfk 
} from './commands.js';

// Re-export types and setMaxConcurrentUsers
export type { BotConfig } from './types.js';
export { setMaxConcurrentUsers } from './rate-limiter.js';

export function createBot(config: BotConfig) {
  const bot = new Telegraf(config.telegramToken);
  let botUsername = '';
  let botId = 0;
  
  // Set proxy URL for API requests (secrets isolation)
  if (config.proxyUrl) {
    setProxyUrl(config.proxyUrl);
  }
  
  // Initialize LLM for smart reactions and autonomous thoughts
  const llmClient = new OpenAI({
    baseURL: config.baseUrl,
    apiKey: config.apiKey,
  });
  initReactionLLM(llmClient, config.model);
  setOpenAIClient(llmClient);
  
  // Set max concurrent users from config
  if (config.maxConcurrentUsers) {
    setMaxConcurrentUsers(config.maxConcurrentUsers);
  }
  
  // Session to chatId mapping
  const sessionChats = new Map<string, number>();
  
  // Per-user agents with separate workspaces
  const userAgents = new Map<number, ReActAgent>();
  
  bot.telegram.getMe().then(me => {
    botUsername = me.username || '';
    botId = me.id;
    console.log(`[bot] @${botUsername} (${botId})`);
  });
  
  // Get or create agent for user (with personal workspace)
  function getAgent(userId: number): ReActAgent {
    if (userAgents.has(userId)) {
      return userAgents.get(userId)!;
    }
    
    // Create user workspace
    const userCwd = join(config.cwd, String(userId));
    if (!existsSync(userCwd)) {
      mkdirSync(userCwd, { recursive: true });
      console.log(`[bot] Created workspace for user ${userId}: ${userCwd}`);
    }
    
    const agent = new ReActAgent({
      baseUrl: config.baseUrl,
      apiKey: config.apiKey,
      model: config.model,
      cwd: userCwd,
      zaiApiKey: config.zaiApiKey,
      tavilyApiKey: config.tavilyApiKey,
      exposedPorts: config.exposedPorts,
    });
    
    userAgents.set(userId, agent);
    return agent;
  }
  
  // Set up NON-BLOCKING approval callback - just shows buttons
  setApprovalCallback((chatId, commandId, command, reason) => {
    console.log(`[approval] Showing buttons for command ${commandId}`);
    console.log(`[approval] Command: ${command}`);
    console.log(`[approval] Reason: ${reason}`);
    
    const message = `⚠️ <b>Approval Required</b>\n\n` +
      `<b>Reason:</b> ${escapeHtml(reason)}\n\n` +
      `<pre>${escapeHtml(command)}</pre>\n\n` +
      `Click to execute or deny:`;
    
    bot.telegram.sendMessage(chatId, message, {
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [[
          { text: '✅ Execute', callback_data: `exec:${commandId}` },
          { text: '❌ Deny', callback_data: `deny:${commandId}` },
        ]],
      },
    }).then(sent => {
      console.log(`[approval] Message sent, id: ${sent.message_id}`);
    }).catch(e => {
      console.error('[approval] Failed to send:', e);
    });
  });
  
  // Set up ask callback for ask_user tool
  setAskCallback(async (sessionId, question, options) => {
    const chatId = sessionChats.get(sessionId);
    if (!chatId) {
      throw new Error('No chat found for session');
    }
    
    const id = `ask_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    
    const promise = new Promise<string>((resolve, reject) => {
      const timeout = setTimeout(() => {
        pendingQuestions.delete(id);
        reject(new Error('Question timeout'));
      }, CONFIG.timeouts.questionPending);
      
      pendingQuestions.set(id, {
        id,
        resolve: (answer) => {
          clearTimeout(timeout);
          pendingQuestions.delete(id);
          resolve(answer);
        },
      });
    });
    
    const keyboard = options.map((opt, i) => [{
      text: opt,
      callback_data: `ask:${id}:${i}`,
    }]);
    
    await bot.telegram.sendMessage(chatId, `❓ ${escapeHtml(question)}`, {
      parse_mode: 'HTML',
      reply_markup: { inline_keyboard: keyboard },
    });
    
    return promise;
  });
  
  // Set up send file callback
  setSendFileCallback(async (chatId, filePath, caption) => {
    const { createReadStream } = await import('fs');
    await bot.telegram.sendDocument(chatId, {
      source: createReadStream(filePath),
      filename: filePath.split('/').pop() || 'file',
    }, {
      caption: caption || undefined,
    });
  });
  
  // Set up send DM callback (for sending private messages)
  setSendDmCallback(async (userId, message) => {
    try {
      await safeSend(userId, async () => {
        await bot.telegram.sendMessage(userId, message, { parse_mode: 'HTML' });
      });
      return true;
    } catch (e: any) {
      console.log(`[send_dm] Failed to send to ${userId}: ${e.message?.slice(0, 50)}`);
      return false;
    }
  });
  
  // Set up delete message callback
  setDeleteMessageCallback(async (chatId, messageId) => {
    try {
      await bot.telegram.deleteMessage(chatId, messageId);
      return true;
    } catch (e: any) {
      console.log(`[delete] Failed: ${e.message?.slice(0, 50)}`);
      return false;
    }
  });
  
  // Set up edit message callback
  setEditMessageCallback(async (chatId, messageId, newText) => {
    try {
      await bot.telegram.editMessageText(chatId, messageId, undefined, newText, { parse_mode: 'HTML' });
      return true;
    } catch (e: any) {
      console.log(`[edit] Failed: ${e.message?.slice(0, 50)}`);
      return false;
    }
  });
  
  // Set up scheduler callback for sending messages
  setSendMessageCallback(async (chatId, text) => {
    await bot.telegram.sendMessage(chatId, text);
  });
  
  // Start the task scheduler
  startScheduler();
  
  // Start the process manager (cleanup inactive users)
  startProcessManager();
  
  // Start Docker sandbox manager (async, fire-and-forget)
  startSandboxManager().catch(err => {
    console.error('[sandbox] Failed to start:', err.message);
  });
  
  // Setup callback handlers (execute, deny, ask)
  setupAllHandlers(bot);
  
  // Track reactions to bot's messages
  bot.on('message_reaction', async (ctx) => {
    try {
      const update = ctx.update as any;
      const reaction = update.message_reaction;
      if (!reaction) return;
      
      // Get reaction info
      const chatId = reaction.chat?.id;
      const userId = reaction.user?.id;
      const username = reaction.user?.username || reaction.user?.first_name || 'anon';
      const newReactions = reaction.new_reaction || [];
      const oldReactions = reaction.old_reaction || [];
      
      // Find what reaction was added
      const addedEmojis = newReactions
        .filter((r: any) => r.type === 'emoji')
        .map((r: any) => r.emoji);
      
      if (addedEmojis.length > 0) {
        const emoji = addedEmojis.join('');
        console.log(`[reaction-received] ${username} reacted ${emoji}`);
        
        // Save to chat history (per-chat)
        saveChatMessage(username, `отреагировал ${emoji}`, false, chatId);
      }
    } catch (e) {
      // Ignore reaction errors
    }
  });
  
  // React to messages in groups (even if not addressed to bot)
  bot.on('text', async (ctx, next) => {
    const msg = ctx.message;
    const chatType = msg?.chat?.type;
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    
    if (isGroup && msg?.text) {
      // Remember this group for autonomous messages
      setMainGroupChatId(msg.chat.id);
      
      // Don't react to own messages
      if (msg.from?.id === botId) {
        return next();
      }
      
      // Save to chat history regardless (per-chat)
      const username = msg.from?.username || msg.from?.first_name || 'anon';
      const chatId = ctx.chat?.id;
      saveChatMessage(username, msg.text, false, chatId);
      
      // Check if should react
      if (shouldReact(msg.text)) {
        const username = msg.from?.username || msg.from?.first_name || 'anon';
        const reaction = await getSmartReaction(msg.text, username);
        
        try {
          await ctx.telegram.setMessageReaction(
            msg.chat.id, 
            msg.message_id, 
            [{ type: 'emoji', emoji: reaction as any }]
          );
          console.log(`[reaction] ${reaction} to "${msg.text.slice(0, 30)}..."`);
        } catch (e: any) {
          console.log(`[reaction] Failed ${reaction}: ${e.message?.slice(0, 50)}`);
        }
      }
    }
    
    return next();
  });
  
  // Check if should respond (groups: @mention, reply, or random ~10%)
  function shouldRespond(ctx: Context & { message?: any }): { respond: boolean; text: string; isRandom?: boolean } {
    const msg = ctx.message;
    if (!msg?.text) return { respond: false, text: '' };
    
    const chatType = msg.chat?.type;
    const isPrivate = chatType === 'private';
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    
    if (isPrivate) {
      return { respond: true, text: msg.text };
    }
    
    if (isGroup) {
      // Check reply to bot (by ID or username)
      const replyMsg = msg.reply_to_message;
      const replyToBot = replyMsg?.from?.id === botId || 
                         replyMsg?.from?.username === botUsername;
      
      // Check @mention
      const mentionsBot = botUsername && msg.text.includes(`@${botUsername}`);
      
      console.log(`[group] reply_to: ${replyMsg?.from?.id}/${replyMsg?.from?.username}, mention: ${mentionsBot}, botId: ${botId}`);
      
      if (replyToBot || mentionsBot) {
        const cleanText = botUsername 
          ? msg.text.replace(new RegExp(`@${botUsername}\\s*`, 'gi'), '').trim()
          : msg.text;
        return { respond: true, text: cleanText || msg.text };
      }
      
      // Random trigger - bot randomly joins conversation
      if (Math.random() < CONFIG.triggers.randomReplyChance && msg.text.length > CONFIG.triggers.minTextForRandom) {
        console.log(`[random] Bot decided to chime in!`);
        return { respond: true, text: msg.text, isRandom: true };
      }
      
      return { respond: false, text: '' };
    }
    
    return { respond: false, text: '' };
  }
  
  // Debug middleware
  bot.use(async (ctx, next) => {
    const updateType = ctx.updateType;
    console.log(`[telegram] Update: ${updateType}`);
    
    if (updateType === 'callback_query') {
      const data = (ctx.callbackQuery as any)?.data;
      console.log(`[telegram] Callback data: ${data}`);
    }
    
    return next();
  });
  
  // Setup commands (/start, /clear, /status, /pending, /afk)
  setupAllCommands(bot, config, botUsername, getAgent);
  
  // Text messages - main handler
  bot.on('text', async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    // Check if bot is AFK
    if (isAfk()) {
      // Still AFK - only react sometimes, don't respond
      const { respond } = shouldRespond(ctx);
      if (respond) {
        // Set a reaction to show we saw the message
        try {
          await ctx.telegram.setMessageReaction(ctx.chat.id, ctx.message.message_id, [{ type: 'emoji', emoji: '💤' as any }]);
        } catch {}
      }
      return;
    }
    
    const { respond, text, isRandom } = shouldRespond(ctx);
    if (!respond || !text) return;
    
    const chatType = ctx.chat?.type;
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    const isPrivate = chatType === 'private';
    
    // Шанс игнорирования (более человечное поведение)
    const ignoreChance = isPrivate ? CONFIG.bot.ignorePrivateChance : CONFIG.bot.ignoreChance;
    if (!isRandom && Math.random() < ignoreChance) {
      console.log(`[bot] Ignoring message from ${userId} (random ignore, ${(ignoreChance * 100).toFixed(0)}% chance)`);
      // Иногда ставим реакцию "видел, но игнорю"
      if (Math.random() < 0.5) {
        try {
          const ignoreEmojis = ['😴', '🙈', '💤', '🤷'] as const;
          const emoji = ignoreEmojis[Math.floor(Math.random() * ignoreEmojis.length)];
          await ctx.telegram.setMessageReaction(ctx.chat.id, ctx.message.message_id, [{ type: 'emoji', emoji: emoji as any }]);
        } catch {}
      }
      return;
    }
    
    // If random trigger, add context hint for the agent
    const username = ctx.from?.username || ctx.from?.first_name || String(userId);
    const userPrefix = `[От: @${username} (${userId})]`;
    
    const messageForAgent = isRandom 
      ? `${userPrefix}\n[Ты случайно увидел это сообщение и решил прокомментировать. НЕ отвечай как на запрос - просто вклинься в разговор, пошути или прокомментируй]\n\n${text}`
      : `${userPrefix}\n${text}`;
    
    const sessionId = userId.toString();
    const messageId = ctx.message.message_id;
    const chatId = ctx.chat.id;
    
    // Check concurrent users limit
    if (!canAcceptUser(userId)) {
      console.log(`[bot] User ${userId} rejected - server busy`);
      try {
        await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '🤔' as any }]);
      } catch {}
      await safeSend(chatId, () => 
        ctx.reply('⏳ Сервер занят, попробуй через минуту', { reply_parameters: { message_id: messageId } })
      );
      return;
    }
    
    // Save chat ID for approval requests
    sessionChats.set(sessionId, chatId);
    
    console.log(`\n[IN] @${username} (${userId}):\n${text}\n`);
    
    // Log to global activity log
    logGlobal(userId, 'message', text.slice(0, CONFIG.messages.logSliceLength));
    
    // Save to chat history (only for private chats, groups are saved in reaction handler)
    if (isPrivate) {
      saveChatMessage(username, text, false, chatId);
    }
    
    // Detect prompt injection attempts
    if (detectPromptInjection(text)) {
      console.log(`[SECURITY] Prompt injection attempt from ${userId}: ${text.slice(0, 50)}`);
      logGlobal(userId, 'INJECTION', text.slice(0, 50));
      try {
        await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '🤨' }]);
      } catch {}
      await safeSend(chatId, () => 
        ctx.reply('Хорошая попытка 😏', { reply_parameters: { message_id: messageId } })
      );
      return;
    }
    
    // Случайная задержка перед ответом (человечное поведение)
    if (Math.random() < CONFIG.bot.delayedResponseChance) {
      const delay = CONFIG.bot.delayedResponseMin + 
        Math.random() * (CONFIG.bot.delayedResponseMax - CONFIG.bot.delayedResponseMin);
      console.log(`[bot] Delayed response for ${userId}, waiting ${Math.round(delay / 1000)}s...`);
      
      // Пока ждем, иногда показываем typing
      const delayTyping = setInterval(() => {
        ctx.sendChatAction('typing').catch(() => {});
      }, 3000);
      
      await new Promise(resolve => setTimeout(resolve, delay));
      clearInterval(delayTyping);
    }
    
    // React with emoji to show we're working on it
    try {
      await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '👀' }]);
    } catch {}
    
    // Mark user as active (rate limiter + process manager)
    markUserActive(userId);
    markProcessUserActive(userId.toString());
    
    // Use lock to prevent concurrent requests from same user
    await withUserLock(userId, async () => {
      // Get agent for this user (creates workspace if needed)
      const agent = getAgent(userId);
      
      // Just send typing action periodically (no status messages to avoid rate limits)
      const typing = setInterval(() => ctx.sendChatAction('typing').catch(() => {}), CONFIG.bot.typingInterval);
      
      // Initialize tool tracker for this user
      toolTrackers.set(userId, { tools: [], lastUpdate: 0 });
      let statusMsgId: number | undefined;
      
      try {
        // Small random delay to feel more human
        const thinkDelay = CONFIG.bot.thinkDelayMin + Math.random() * (CONFIG.bot.thinkDelayMax - CONFIG.bot.thinkDelayMin);
        await new Promise(resolve => setTimeout(resolve, thinkDelay));
        
        // Run agent with tool status updates
        // Pass chatType to restrict dangerous commands in groups
        const response = await agent.run(sessionId, messageForAgent, async (toolName) => {
          logGlobal(userId, 'tool', toolName);
          
          const tracker = toolTrackers.get(userId)!;
          const comment = getToolComment(toolName);
          tracker.tools.push(`${toolEmoji(toolName)} ${comment}`);
          
          const now = Date.now();
          const timeSinceLastUpdate = now - tracker.lastUpdate;
          
          // Update status every N tools AND respect minimum interval (avoid 429)
          if (tracker.tools.length % TOOL_UPDATE_INTERVAL === 1 && timeSinceLastUpdate >= MIN_EDIT_INTERVAL_MS) {
            tracker.lastUpdate = now;
            const statusText = `Working...\n\n${tracker.tools.slice(-6).join('\n')}`;
            
            try {
              if (statusMsgId) {
                // Edit existing message
                await ctx.telegram.editMessageText(chatId, statusMsgId, undefined, statusText);
              } else {
                // Send new status message
                const sent = await ctx.reply(statusText, { reply_parameters: { message_id: messageId } });
                statusMsgId = sent.message_id;
              }
            } catch {}
          }
        }, chatId, chatType as any);
        
        clearInterval(typing);
        
        // Delete status message if exists
        if (statusMsgId) {
          try {
            await ctx.telegram.deleteMessage(chatId, statusMsgId);
          } catch {}
        }
        
        // Clear tracker
        toolTrackers.delete(userId);
        
        // Change reaction to done (random positive emoji - all tested working!)
        try {
          await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: getRandomDoneEmoji() as any }]);
        } catch {}
        
        // Send final response with rate limiting
        const finalResponse = response || '(no response)';
        console.log(`[OUT] → @${username}:\n${finalResponse}\n`);
        const html = mdToHtml(finalResponse);
        const parts = splitMessage(html);
        
        for (let i = 0; i < parts.length; i++) {
          const sent = await safeSend(chatId, () => 
            ctx.reply(parts[i], { 
              parse_mode: 'HTML',
              reply_parameters: i === 0 ? { message_id: messageId } : undefined
            })
          );
          
          // Record message for manage_message tool
          if (sent?.message_id) {
            recordBotMessage(chatId, sent.message_id);
          }
          
          if (!sent && i === 0) {
            // Fallback to plain text
            const fallback = await safeSend(chatId, () => 
              ctx.reply(finalResponse.slice(0, 4000), { reply_parameters: { message_id: messageId } })
            );
            if (fallback?.message_id) {
              recordBotMessage(chatId, fallback.message_id);
            }
            break;
          }
        }
        
        // Save bot response to chat history (per-chat)
        saveChatMessage('LocalTopSH', finalResponse.slice(0, CONFIG.messages.historySliceLength), true, chatId);
        
        // Periodic troll message
        if (shouldTroll()) {
          await new Promise(r => setTimeout(r, CONFIG.bot.trollDelay));  // Wait a bit
          const trollMsg = getTrollMessage();
          const trollSent = await safeSend(chatId, () => ctx.reply(trollMsg));
          if (trollSent?.message_id) recordBotMessage(chatId, trollSent.message_id);
          saveChatMessage('LocalTopSH', trollMsg, true, chatId);
        }
      } catch (e: any) {
        clearInterval(typing);
        console.error('[bot] Error:', e.message);
        
        // Delete status message if exists
        if (statusMsgId) {
          try {
            await ctx.telegram.deleteMessage(chatId, statusMsgId);
          } catch {}
        }
        toolTrackers.delete(userId);
        
        // Change reaction to error
        try {
          await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '👎' as any }]);
        } catch {}
        
        const errorComment = getToolComment('error', true);
        await safeSend(chatId, () => 
          ctx.reply(`❌ ${errorComment}\n\n${e.message?.slice(0, 200)}`, { reply_parameters: { message_id: messageId } })
        );
      } finally {
        // Mark user as inactive when done
        markUserInactive(userId);
      }
    });
  });
  
  // Global error handler - prevent crashes
  bot.catch((err: any, ctx) => {
    console.error('[bot] Unhandled error:', err.message);
    // Don't try to reply - might cause more rate limits
  });
  
  // Start autonomous messages
  startAutonomousMessages(bot);
  
  return bot;
}
