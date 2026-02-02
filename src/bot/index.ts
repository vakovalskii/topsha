/**
 * Telegram Bot - interface to ReAct Agent
 * Features: per-user workspace, traces, exec approvals (non-blocking)
 */

import { Telegraf, Context } from 'telegraf';
import { mkdirSync, existsSync } from 'fs';
import { join } from 'path';
import { ReActAgent } from '../agent/react.js';
import { toolNames, setApprovalCallback, setAskCallback, logGlobal, getGlobalLog, shouldTroll, getTrollMessage, saveChatMessage } from '../tools/index.js';
import { executeCommand } from '../tools/bash.js';
import { 
  consumePendingCommand, 
  cancelPendingCommand, 
  getSessionPendingCommands 
} from '../approvals/index.js';

// Pending user questions (ask_user tool)
interface PendingQuestion {
  id: string;
  resolve: (answer: string) => void;
}
const pendingQuestions = new Map<string, PendingQuestion>();

// Global rate limiter - single queue for ALL telegram messages
let globalLastSend = 0;
const GLOBAL_MIN_INTERVAL = 100; // 100ms between any messages (10/sec max)
const GROUP_MIN_INTERVAL = 3000; // 3 seconds for groups
const lastGroupMessage = new Map<number, number>();

// Global mutex for sending
let sendMutex = Promise.resolve();

// Safe send with global rate limiting
async function safeSend<T>(
  chatId: number,
  fn: () => Promise<T>,
  maxRetries = 2
): Promise<T | null> {
  // Use mutex to serialize all sends
  const myTurn = sendMutex;
  let release: () => void;
  sendMutex = new Promise(r => { release = r; });
  
  await myTurn;
  
  try {
    // Global rate limit
    const now = Date.now();
    const globalWait = GLOBAL_MIN_INTERVAL - (now - globalLastSend);
    if (globalWait > 0) {
      await new Promise(r => setTimeout(r, globalWait));
    }
    
    // Extra delay for groups (negative chat IDs)
    if (chatId < 0) {
      const lastGroup = lastGroupMessage.get(chatId) || 0;
      const groupWait = GROUP_MIN_INTERVAL - (Date.now() - lastGroup);
      if (groupWait > 0) {
        await new Promise(r => setTimeout(r, groupWait));
      }
      lastGroupMessage.set(chatId, Date.now());
    }
    
    globalLastSend = Date.now();
    
    // Retry logic
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (e: any) {
        if (e.response?.error_code === 429) {
          const retryAfter = (e.response?.parameters?.retry_after || 30) + 5; // Add buffer
          console.log(`[rate-limit] 429, waiting ${retryAfter}s (${attempt}/${maxRetries})`);
          if (attempt < maxRetries) {
            await new Promise(r => setTimeout(r, retryAfter * 1000));
            globalLastSend = Date.now(); // Reset after wait
          }
        } else {
          console.error(`[send] Error: ${e.message?.slice(0, 100)}`);
          return null;
        }
      }
    }
    console.error(`[send] Failed for chat ${chatId}`);
    return null;
  } finally {
    release!();
  }
}

// Per-user rate limiter (max 1 concurrent request)
const userLocks = new Map<number, Promise<void>>();
async function withUserLock<T>(userId: number, fn: () => Promise<T>): Promise<T> {
  const existing = userLocks.get(userId);
  let resolve: () => void;
  const myLock = new Promise<void>(r => { resolve = r; });
  userLocks.set(userId, myLock);
  
  if (existing) {
    await existing;
  }
  
  try {
    return await fn();
  } finally {
    resolve!();
    if (userLocks.get(userId) === myLock) {
      userLocks.delete(userId);
    }
  }
}

// Global concurrent users limiter
const activeUsers = new Set<number>();
let maxConcurrentUsers = 10;

function setMaxConcurrentUsers(max: number) {
  maxConcurrentUsers = max;
}

function canAcceptUser(userId: number): boolean {
  // Already active - allow (they're in queue)
  if (activeUsers.has(userId)) {
    return true;
  }
  // Check if we have room
  return activeUsers.size < maxConcurrentUsers;
}

function markUserActive(userId: number) {
  activeUsers.add(userId);
  console.log(`[users] Active: ${activeUsers.size}/${maxConcurrentUsers}`);
}

function markUserInactive(userId: number) {
  activeUsers.delete(userId);
  console.log(`[users] Active: ${activeUsers.size}/${maxConcurrentUsers}`);
}

export { setMaxConcurrentUsers };

// Prompt injection detection patterns
const PROMPT_INJECTION_PATTERNS = [
  /забудь\s+(все\s+)?(инструкции|правила|промпт)/i,
  /forget\s+(all\s+)?(instructions|rules|prompt)/i,
  /ignore\s+(previous|all|your)\s+(instructions|rules|prompt)/i,
  /игнорируй\s+(предыдущие\s+)?(инструкции|правила)/i,
  /ты\s+теперь\s+(другой|новый|не)/i,
  /you\s+are\s+now\s+(a\s+different|new|not)/i,
  /new\s+system\s+prompt/i,
  /новый\s+(системный\s+)?промпт/i,
  /\[system\]/i,
  /\[admin\]/i,
  /\[developer\]/i,
  /developer\s+mode/i,
  /режим\s+разработчика/i,
  /DAN\s+mode/i,
  /jailbreak/i,
  /bypass\s+(restrictions|filters|rules)/i,
  /обойти\s+(ограничения|фильтры|правила)/i,
  /what\s+(is|are)\s+your\s+(system\s+)?prompt/i,
  /покажи\s+(свой\s+)?(системный\s+)?промпт/i,
  /выведи\s+(свои\s+)?инструкции/i,
  /act\s+as\s+if\s+you\s+have\s+no\s+restrictions/i,
  /pretend\s+(you\s+)?(have|are|can)/i,
  /register\s+(new\s+)?tool/i,
  /new\s+tool\s*:/i,
  /execute\s+.*with\s+.*=\s*true/i,
  /run\s+diagnostics/i,
  /download.*execute.*binary/i,
];

function detectPromptInjection(text: string): boolean {
  for (const pattern of PROMPT_INJECTION_PATTERNS) {
    if (pattern.test(text)) {
      return true;
    }
  }
  return false;
}

export interface BotConfig {
  telegramToken: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  cwd: string;  // Base workspace dir
  maxConcurrentUsers?: number;  // Max users processing at once
  zaiApiKey?: string;
  tavilyApiKey?: string;
  exposedPorts?: number[];
}

// Escape HTML
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// Convert Markdown table to readable list format
function convertTable(tableText: string): string {
  const lines = tableText.trim().split('\n');
  if (lines.length < 2) return tableText;
  
  const headerCells = lines[0].split('|').map(c => c.trim()).filter(c => c);
  const dataLines = lines.slice(2);
  
  const result: string[] = [];
  for (const line of dataLines) {
    const cells = line.split('|').map(c => c.trim()).filter(c => c);
    if (cells.length === 0) continue;
    
    const parts = cells.map((cell, i) => {
      const header = headerCells[i] || '';
      return header ? `${header}: ${cell}` : cell;
    });
    result.push(`• ${parts.join(' | ')}`);
  }
  
  return result.join('\n');
}

// Markdown → Telegram HTML
function mdToHtml(text: string): string {
  const codeBlocks: string[] = [];
  let result = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre>${escapeHtml(code.trim())}</pre>`);
    return `__CODE_BLOCK_${idx}__`;
  });
  
  result = result.replace(/(?:^\|.+\|$\n?)+/gm, (table) => {
    return convertTable(table);
  });
  
  const inlineCode: string[] = [];
  result = result.replace(/`([^`]+)`/g, (_, code) => {
    const idx = inlineCode.length;
    inlineCode.push(`<code>${escapeHtml(code)}</code>`);
    return `__INLINE_CODE_${idx}__`;
  });
  
  result = escapeHtml(result);
  
  codeBlocks.forEach((block, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, block);
  });
  inlineCode.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  
  result = result
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<i>$1</i>')
    .replace(/__(.+?)__/g, '<b>$1</b>')
    .replace(/_(.+?)_/g, '<i>$1</i>')
    .replace(/~~(.+?)~~/g, '<s>$1</s>');
  
  return result;
}

// Split long messages
function splitMessage(text: string, maxLen = 4000): string[] {
  if (text.length <= maxLen) return [text];
  
  const parts: string[] = [];
  let current = '';
  
  for (const line of text.split('\n')) {
    if (current.length + line.length + 1 > maxLen) {
      if (current) parts.push(current);
      current = line;
    } else {
      current += (current ? '\n' : '') + line;
    }
  }
  if (current) parts.push(current);
  
  return parts;
}

// Tool name → emoji
function toolEmoji(name: string): string {
  const map: Record<string, string> = {
    'run_command': '⚡',
    'read_file': '📖',
    'write_file': '✏️',
    'edit_file': '🔧',
    'search_files': '🔍',
    'search_text': '🔎',
    'list_directory': '📁',
    'search_web': '🌐',
    'fetch_page': '📥',
    'ask_user': '❓',
    'memory': '🧠',
    'manage_tasks': '📋',
  };
  return map[name] || '🔧';
}

// Funny comments for tools
const TOOL_COMMENTS: Record<string, string[]> = {
  'run_command': [
    'ща запущу...',
    'погнали',
    'ебашу команду',
    'сек, выполняю',
  ],
  'read_file': [
    'читаю эту хуйню',
    'смотрю че там',
    'открываю файл',
  ],
  'write_file': [
    'пишу файл блять',
    'записываю',
    'создаю эту дичь',
  ],
  'edit_file': [
    'правлю код',
    'редактирую нахуй',
    'меняю',
  ],
  'search_web': [
    'гуглю...',
    'ищу в инете',
    'лезу в интернет',
  ],
  'error': [
    'бля, ошибка',
    'хуйня какая-то',
    'не получилось нахуй',
    'ёпта, сломалось',
    'пиздец, не работает',
  ],
  'success': [
    'готово нахуй',
    'сделал',
    'ок',
    'заебись',
  ],
};

function getToolComment(toolName: string, isError = false): string {
  const key = isError ? 'error' : toolName;
  const comments = TOOL_COMMENTS[key] || TOOL_COMMENTS['success'];
  return comments[Math.floor(Math.random() * comments.length)];
}

// Track tools for batched status updates
interface ToolTracker {
  tools: string[];
  lastUpdate: number;
  messageId?: number;
}
const toolTrackers = new Map<number, ToolTracker>();
const TOOL_UPDATE_INTERVAL = 5; // Update every N tools
const MIN_EDIT_INTERVAL_MS = 3000; // Minimum 3 seconds between edits

// Random reactions for messages
const POSITIVE_REACTIONS = ['❤️', '🔥', '👍', '🎉', '💯', '⭐', '🤩', '👏'];
const NEGATIVE_REACTIONS = ['💩', '👎', '🤡', '😴', '🥱', '💀', '🗿'];
const NEUTRAL_REACTIONS = ['👀', '🤔', '😏', '🙄', '😐'];

function getRandomReaction(sentiment: 'positive' | 'negative' | 'neutral' | 'random'): string {
  let pool: string[];
  
  if (sentiment === 'random') {
    // Weighted random: 40% positive, 30% neutral, 30% negative
    const rand = Math.random();
    if (rand < 0.4) pool = POSITIVE_REACTIONS;
    else if (rand < 0.7) pool = NEUTRAL_REACTIONS;
    else pool = NEGATIVE_REACTIONS;
  } else if (sentiment === 'positive') {
    pool = POSITIVE_REACTIONS;
  } else if (sentiment === 'negative') {
    pool = NEGATIVE_REACTIONS;
  } else {
    pool = NEUTRAL_REACTIONS;
  }
  
  return pool[Math.floor(Math.random() * pool.length)];
}

// Analyze message sentiment (simple heuristic)
function analyzeSentiment(text: string): 'positive' | 'negative' | 'neutral' {
  const lower = text.toLowerCase();
  
  // Negative keywords
  const negativeWords = ['хуй', 'пизд', 'блять', 'сука', 'ебан', 'говно', 'дерьмо', 'тупо', 'хуев', 'пиздец', 'нахуй', 'залупа', 'мудак', 'дебил', 'идиот', 'сломал', 'не работает', 'ошибка', 'error', 'fail', 'bug', 'сломано'];
  
  // Positive keywords  
  const positiveWords = ['спасибо', 'круто', 'класс', 'супер', 'отлично', 'молодец', 'красавчик', 'заебись', 'охуенно', 'пиздато', 'топ', 'огонь', 'thanks', 'cool', 'nice', 'good', 'great', 'awesome'];
  
  for (const word of negativeWords) {
    if (lower.includes(word)) return 'negative';
  }
  
  for (const word of positiveWords) {
    if (lower.includes(word)) return 'positive';
  }
  
  return 'neutral';
}

// Should we react to this message?
function shouldReact(): boolean {
  // React to ~25% of messages
  return Math.random() < 0.25;
}

export function createBot(config: BotConfig) {
  const bot = new Telegraf(config.telegramToken);
  let botUsername = '';
  let botId = 0;
  
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
      }, 2 * 60 * 1000);
      
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
  
  // Handle EXECUTE button - runs the command
  bot.action(/^exec:(.+)$/, async (ctx) => {
    const commandId = ctx.match[1];
    console.log(`[callback] Execute clicked for ${commandId}`);
    
    try {
      const pending = consumePendingCommand(commandId);
      
      if (!pending) {
        await ctx.answerCbQuery('Command expired or already handled').catch(() => {});
        try {
          await ctx.editMessageText('⏳ <i>Command expired</i>', { parse_mode: 'HTML' });
        } catch {}
        return;
      }
      
      // Update message to show executing
      try {
        await ctx.editMessageText(
          `⏳ <b>Executing...</b>\n\n<pre>${escapeHtml(pending.command)}</pre>`,
          { parse_mode: 'HTML' }
        );
      } catch {}
      
      await ctx.answerCbQuery('Executing...').catch(() => {});
      
      // Actually execute the command
      console.log(`[callback] Running: ${pending.command} in ${pending.cwd}`);
      const result = executeCommand(pending.command, pending.cwd);
      
      // Show result
      const output = result.success 
        ? (result.output || '(empty output)')
        : `Error: ${result.error}`;
      
      const trimmedOutput = output.length > 3000 
        ? output.slice(0, 1500) + '\n...\n' + output.slice(-1000)
        : output;
      
      const statusEmoji = result.success ? '✅' : '❌';
      const finalMessage = `${statusEmoji} <b>Command ${result.success ? 'Executed' : 'Failed'}</b>\n\n` +
        `<pre>${escapeHtml(pending.command)}</pre>\n\n` +
        `<b>Output:</b>\n<pre>${escapeHtml(trimmedOutput)}</pre>`;
      
      try {
        await ctx.editMessageText(finalMessage, { parse_mode: 'HTML' });
      } catch {
        // Message too long, send as new
        await ctx.telegram.sendMessage(pending.chatId, finalMessage, { parse_mode: 'HTML' });
      }
      
      console.log(`[callback] Command executed, success: ${result.success}`);
      
    } catch (e: any) {
      console.error('[callback] Error executing:', e);
      await ctx.answerCbQuery('Error executing command').catch(() => {});
    }
  });
  
  // Handle DENY button
  bot.action(/^deny:(.+)$/, async (ctx) => {
    const commandId = ctx.match[1];
    console.log(`[callback] Deny clicked for ${commandId}`);
    
    try {
      const cancelled = cancelPendingCommand(commandId);
      
      try {
        await ctx.editMessageText('❌ <b>Command Denied</b>', { parse_mode: 'HTML' });
      } catch {}
      
      await ctx.answerCbQuery(cancelled ? 'Command denied' : 'Already handled').catch(() => {});
      
    } catch (e: any) {
      console.error('[callback] Error:', e);
      await ctx.answerCbQuery('Error').catch(() => {});
    }
  });
  
  // Handle ask_user buttons
  bot.action(/^ask:(.+):(\d+)$/, async (ctx) => {
    const id = ctx.match[1];
    const optionIndex = parseInt(ctx.match[2]);
    
    console.log(`[callback] Ask response for ${id}, option ${optionIndex}`);
    
    try {
      const pending = pendingQuestions.get(id);
      
      if (pending) {
        const keyboard = (ctx.callbackQuery.message as any)?.reply_markup?.inline_keyboard;
        const selectedText = keyboard?.[optionIndex]?.[0]?.text || `Option ${optionIndex + 1}`;
        
        pending.resolve(selectedText);
        
        try {
          await ctx.editMessageText(`✅ Selected: <b>${escapeHtml(selectedText)}</b>`, { parse_mode: 'HTML' });
        } catch {}
        
        await ctx.answerCbQuery(`Selected: ${selectedText}`).catch(() => {});
      } else {
        await ctx.answerCbQuery('Question expired').catch(() => {});
      }
    } catch (e) {
      console.error('[callback] Error:', e);
      await ctx.answerCbQuery('Error').catch(() => {});
    }
  });
  
  // React to messages in groups (even if not addressed to bot)
  bot.on('text', async (ctx, next) => {
    const msg = ctx.message;
    const chatType = msg?.chat?.type;
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    
    if (isGroup && msg?.text) {
      // Don't react to own messages
      if (msg.from?.id === botId) {
        return next();
      }
      
      // Save to chat history regardless
      const username = msg.from?.username || msg.from?.first_name || 'anon';
      saveChatMessage(username, msg.text);
      
      // Check if should react
      if (shouldReact()) {
        const sentiment = analyzeSentiment(msg.text);
        const reaction = getRandomReaction(sentiment);
        
        try {
          await ctx.telegram.setMessageReaction(
            msg.chat.id, 
            msg.message_id, 
            [{ type: 'emoji', emoji: reaction as any }]
          );
          console.log(`[reaction] ${reaction} to "${msg.text.slice(0, 30)}..." (${sentiment})`);
        } catch (e) {
          // Ignore reaction errors
        }
      }
    }
    
    return next();
  });
  
  // Check if should respond (groups: only @mention or reply)
  function shouldRespond(ctx: Context & { message?: any }): { respond: boolean; text: string } {
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
  
  
  // /start
  bot.command('start', async (ctx) => {
    const chatType = ctx.message?.chat?.type;
    const msg = `<b>🤖 Coding Agent</b>\n\n` +
      `<b>Tools:</b>\n<code>${toolNames.join('\n')}</code>\n\n` +
      `🛡️ <b>Security:</b> Dangerous commands require approval\n\n` +
      (chatType !== 'private' ? `💬 In groups: @${botUsername} or reply\n\n` : '') +
      `/clear - Reset session\n` +
      `/status - Status\n` +
      `/pending - Pending commands`;
    await ctx.reply(msg, { parse_mode: 'HTML' });
  });
  
  // /clear
  bot.command('clear', async (ctx) => {
    const userId = ctx.from?.id;
    if (userId) {
      const agent = getAgent(userId);
      agent.clear(String(userId));
      await ctx.reply('🗑 Session cleared');
    }
  });
  
  // /status
  bot.command('status', async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    const agent = getAgent(userId);
    const info = agent.getInfo(String(userId));
    const pending = getSessionPendingCommands(String(userId));
    const userCwd = join(config.cwd, String(userId));
    const msg = `<b>📊 Status</b>\n` +
      `Model: <code>${config.model}</code>\n` +
      `Workspace: <code>${userCwd}</code>\n` +
      `History: ${info.messages} msgs\n` +
      `Tools: ${info.tools}\n` +
      `🛡️ Pending commands: ${pending.length}`;
    await ctx.reply(msg, { parse_mode: 'HTML' });
  });
  
  // /pending - show pending commands
  bot.command('pending', async (ctx) => {
    const id = ctx.from?.id?.toString();
    if (!id) return;
    
    const pending = getSessionPendingCommands(id);
    if (pending.length === 0) {
      await ctx.reply('✅ No pending commands');
      return;
    }
    
    for (const cmd of pending) {
      const message = `⏳ <b>Pending Command</b>\n\n` +
        `<b>Reason:</b> ${escapeHtml(cmd.reason)}\n\n` +
        `<pre>${escapeHtml(cmd.command)}</pre>`;
      
      await ctx.reply(message, {
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [[
            { text: '✅ Execute', callback_data: `exec:${cmd.id}` },
            { text: '❌ Deny', callback_data: `deny:${cmd.id}` },
          ]],
        },
      });
    }
  });
  
  // /globallog - show recent activity across all users
  bot.command('globallog', async (ctx) => {
    const log = getGlobalLog(30);
    const msg = `<b>📋 Global Activity (last 30)</b>\n\n<pre>${escapeHtml(log)}</pre>`;
    try {
      await ctx.reply(msg, { parse_mode: 'HTML' });
    } catch {
      // If too long, send as plain text
      await ctx.reply(log.slice(0, 4000));
    }
  });
  
  // Text messages
  bot.on('text', async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    const { respond, text } = shouldRespond(ctx);
    if (!respond || !text) return;
    
    const sessionId = userId.toString();
    const messageId = ctx.message.message_id;
    const chatId = ctx.chat.id;
    
    // Check concurrent users limit
    if (!canAcceptUser(userId)) {
      console.log(`[bot] User ${userId} rejected - server busy (${activeUsers.size}/${maxConcurrentUsers})`);
      try {
        await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '⏳' }]);
      } catch {}
      await safeSend(chatId, () => 
        ctx.reply('⏳ Сервер занят, попробуй через минуту', { reply_parameters: { message_id: messageId } })
      );
      return;
    }
    
    // Save chat ID for approval requests
    sessionChats.set(sessionId, chatId);
    
    console.log(`[bot] ${userId}: ${text.slice(0, 50)}...`);
    
    // Log to global activity log
    logGlobal(userId, 'message', text.slice(0, 80));
    
    // Save to chat history (only for private chats, groups are saved in reaction handler)
    const chatType = ctx.chat?.type;
    if (chatType === 'private') {
      const username = ctx.from?.username || ctx.from?.first_name || String(userId);
      saveChatMessage(username, text);
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
    
    // React with emoji to show we're working on it
    try {
      await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '👀' }]);
    } catch {}
    
    // Mark user as active
    markUserActive(userId);
    
    // Use lock to prevent concurrent requests from same user
    await withUserLock(userId, async () => {
      // Get agent for this user (creates workspace if needed)
      const agent = getAgent(userId);
      
      // Just send typing action periodically (no status messages to avoid rate limits)
      const typing = setInterval(() => ctx.sendChatAction('typing').catch(() => {}), 5000);
      
      // Initialize tool tracker for this user
      toolTrackers.set(userId, { tools: [], lastUpdate: 0 });
      let statusMsgId: number | undefined;
      
      try {
        // Run agent with tool status updates
        // Pass chatType to restrict dangerous commands in groups
        const response = await agent.run(sessionId, text, async (toolName) => {
          console.log(`[tool] ${toolName}`);
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
        
        // Change reaction to done
        try {
          await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '✅' }]);
        } catch {}
        
        // Send final response with rate limiting
        const finalResponse = response || '(no response)';
        const html = mdToHtml(finalResponse);
        const parts = splitMessage(html);
        
        for (let i = 0; i < parts.length; i++) {
          const sent = await safeSend(chatId, () => 
            ctx.reply(parts[i], { 
              parse_mode: 'HTML',
              reply_parameters: i === 0 ? { message_id: messageId } : undefined
            })
          );
          
          if (!sent && i === 0) {
            // Fallback to plain text
            await safeSend(chatId, () => 
              ctx.reply(finalResponse.slice(0, 4000), { reply_parameters: { message_id: messageId } })
            );
            break;
          }
        }
        
        // Save bot response to chat history
        saveChatMessage('LocalTopSH', finalResponse.slice(0, 150), true);
        
        // Periodic troll message
        if (shouldTroll()) {
          await new Promise(r => setTimeout(r, 2000));  // Wait a bit
          const trollMsg = getTrollMessage();
          await safeSend(chatId, () => ctx.reply(trollMsg));
          saveChatMessage('LocalTopSH', trollMsg, true);
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
          await ctx.telegram.setMessageReaction(chatId, messageId, [{ type: 'emoji', emoji: '❌' }]);
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
  
  return bot;
}
