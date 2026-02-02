/**
 * Telegram Bot - interface to ReAct Agent
 * Features: groups, reply, traces, exec approvals (non-blocking)
 */

import { Telegraf, Context } from 'telegraf';
import { ReActAgent } from '../agent/react.js';
import { toolNames, setApprovalCallback, setAskCallback } from '../tools/index.js';
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

export interface BotConfig {
  telegramToken: string;
  baseUrl: string;
  apiKey: string;
  model: string;
  cwd: string;
  zaiApiKey?: string;
  tavilyApiKey?: string;
  allowedUsers?: number[];
  allowedGroups?: number[];  // Groups where anyone can use bot
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
  };
  return map[name] || '🔧';
}

export function createBot(config: BotConfig) {
  const bot = new Telegraf(config.telegramToken);
  let botUsername = '';
  
  // Session to chatId mapping
  const sessionChats = new Map<string, number>();
  
  bot.telegram.getMe().then(me => {
    botUsername = me.username || '';
    console.log(`[bot] @${botUsername}`);
  });
  
  const agent = new ReActAgent({
    baseUrl: config.baseUrl,
    apiKey: config.apiKey,
    model: config.model,
    cwd: config.cwd,
    zaiApiKey: config.zaiApiKey,
    tavilyApiKey: config.tavilyApiKey,
    exposedPorts: config.exposedPorts,
  });
  
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
    
    if (isGroup && botUsername) {
      const replyToBot = msg.reply_to_message?.from?.username === botUsername;
      const mentionsBot = msg.text.includes(`@${botUsername}`);
      
      if (replyToBot || mentionsBot) {
        const cleanText = msg.text.replace(new RegExp(`@${botUsername}\\s*`, 'gi'), '').trim();
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
  
  // Auth middleware
  bot.use(async (ctx, next) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    const chatId = ctx.chat?.id;
    const chatType = (ctx.message as any)?.chat?.type || ctx.chat?.type;
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    
    // In allowed groups - everyone can use
    if (isGroup && chatId && config.allowedGroups?.includes(chatId)) {
      return next();
    }
    
    // Check allowed users
    if (config.allowedUsers?.length && !config.allowedUsers.includes(userId)) {
      if (chatType === 'private') {
        return ctx.reply('🚫 Access denied');
      }
      return;  // Ignore in non-allowed groups
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
    const id = ctx.from?.id?.toString();
    if (id) {
      agent.clear(id);
      await ctx.reply('🗑 Session cleared');
    }
  });
  
  // /status
  bot.command('status', async (ctx) => {
    const id = ctx.from?.id?.toString();
    if (!id) return;
    
    const info = agent.getInfo(id);
    const pending = getSessionPendingCommands(id);
    const msg = `<b>📊 Status</b>\n` +
      `Model: <code>${config.model}</code>\n` +
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
  
  // Text messages
  bot.on('text', async (ctx) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    const { respond, text } = shouldRespond(ctx);
    if (!respond || !text) return;
    
    const sessionId = userId.toString();
    const messageId = ctx.message.message_id;
    const chatId = ctx.chat.id;
    
    // Save chat ID for approval requests
    sessionChats.set(sessionId, chatId);
    
    console.log(`[bot] ${userId}: ${text.slice(0, 50)}...`);
    
    await ctx.sendChatAction('typing');
    const typing = setInterval(() => ctx.sendChatAction('typing').catch(() => {}), 4000);
    
    let statusMsg: any = null;
    const traces: string[] = [];
    
    try {
      // Pass chatId to agent for approval callbacks
      const response = await agent.run(sessionId, text, async (toolName) => {
        const emoji = toolEmoji(toolName);
        traces.push(`${emoji} ${toolName}`);
        
        const statusText = `<b>Working...</b>\n\n${traces.join('\n')}`;
        
        try {
          if (statusMsg) {
            await ctx.telegram.editMessageText(
              chatId, 
              statusMsg.message_id, 
              undefined, 
              statusText, 
              { parse_mode: 'HTML' }
            );
          } else {
            statusMsg = await ctx.reply(statusText, { 
              parse_mode: 'HTML',
              reply_parameters: { message_id: messageId }
            });
          }
        } catch {}
      }, chatId);  // <-- pass chatId
      
      clearInterval(typing);
      
      if (statusMsg) {
        try { 
          await ctx.telegram.deleteMessage(chatId, statusMsg.message_id); 
        } catch {}
      }
      
      const finalResponse = response || '(no response)';
      const html = mdToHtml(finalResponse);
      const parts = splitMessage(html);
      
      for (let i = 0; i < parts.length; i++) {
        try {
          await ctx.reply(parts[i], { 
            parse_mode: 'HTML',
            reply_parameters: i === 0 ? { message_id: messageId } : undefined
          });
        } catch {
          await ctx.reply(finalResponse.slice(0, 4000), {
            reply_parameters: i === 0 ? { message_id: messageId } : undefined
          });
          break;
        }
      }
    } catch (e: any) {
      clearInterval(typing);
      console.error('[bot] Error:', e);
      await ctx.reply(`❌ ${e.message}`, {
        reply_parameters: { message_id: messageId }
      });
    }
  });
  
  return bot;
}
