/**
 * Telegram Bot - interface to ReAct Agent
 * Features: groups, reply, traces, exec approvals
 */

import { Telegraf, Context } from 'telegraf';
import { ReActAgent } from '../agent/react.js';
import { toolNames, setApprovalCallback, setAskCallback } from '../tools/index.js';
import { requestApproval, handleApproval, cancelSessionApprovals, getSessionApprovals } from '../approvals/index.js';

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
  exposedPorts?: number[];  // ports accessible from external network
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
  
  // Parse header
  const headerCells = lines[0].split('|').map(c => c.trim()).filter(c => c);
  
  // Skip separator line (|---|---|)
  const dataLines = lines.slice(2);
  
  // Convert each row to list item
  const result: string[] = [];
  for (const line of dataLines) {
    const cells = line.split('|').map(c => c.trim()).filter(c => c);
    if (cells.length === 0) continue;
    
    // Format: "• Header1: Value1 | Header2: Value2"
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
  // 1. Extract code blocks first
  const codeBlocks: string[] = [];
  let result = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre>${escapeHtml(code.trim())}</pre>`);
    return `__CODE_BLOCK_${idx}__`;
  });
  
  // 2. Convert tables to list format (before escaping)
  // Match table pattern: lines starting with |
  result = result.replace(/(?:^\|.+\|$\n?)+/gm, (table) => {
    return convertTable(table);
  });
  
  // 3. Extract inline code
  const inlineCode: string[] = [];
  result = result.replace(/`([^`]+)`/g, (_, code) => {
    const idx = inlineCode.length;
    inlineCode.push(`<code>${escapeHtml(code)}</code>`);
    return `__INLINE_CODE_${idx}__`;
  });
  
  // 4. Escape HTML
  result = escapeHtml(result);
  
  // 5. Restore code blocks and inline code
  codeBlocks.forEach((block, i) => {
    result = result.replace(`__CODE_BLOCK_${i}__`, block);
  });
  inlineCode.forEach((code, i) => {
    result = result.replace(`__INLINE_CODE_${i}__`, code);
  });
  
  // 6. Convert markdown formatting
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
  
  // Session to chatId mapping (for sending approval requests)
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
  
  // Set up approval callback for dangerous commands
  setApprovalCallback(async (sessionId, command, reason) => {
    const chatId = sessionChats.get(sessionId);
    if (!chatId) {
      console.log(`[approval] No chat found for session ${sessionId}`);
      return false;
    }
    
    const { id, promise } = requestApproval(sessionId, command, reason);
    
    // Send approval request with inline keyboard
    const message = `⚠️ <b>Dangerous Command Detected</b>\n\n` +
      `<b>Reason:</b> ${escapeHtml(reason)}\n\n` +
      `<pre>${escapeHtml(command)}</pre>\n\n` +
      `Do you want to execute this command?`;
    
    try {
      await bot.telegram.sendMessage(chatId, message, {
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [[
            { text: '✅ Approve', callback_data: `approve:${id}` },
            { text: '❌ Deny', callback_data: `deny:${id}` },
          ]],
        },
      });
    } catch (e) {
      console.error('[approval] Failed to send approval request:', e);
      return false;
    }
    
    return promise;
  });
  
  // Set up ask callback for ask_user tool
  setAskCallback(async (sessionId, question, options) => {
    const chatId = sessionChats.get(sessionId);
    if (!chatId) {
      throw new Error('No chat found for session');
    }
    
    const id = `ask_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    
    // Create promise that resolves when user clicks a button
    const promise = new Promise<string>((resolve, reject) => {
      // Timeout after 2 minutes
      const timeout = setTimeout(() => {
        pendingQuestions.delete(id);
        reject(new Error('Question timeout - no response'));
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
    
    // Create inline keyboard with options
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
  
  // Handle callback queries (approvals + ask_user)
  bot.on('callback_query', async (ctx) => {
    const data = (ctx.callbackQuery as any).data;
    if (!data) return;
    
    try {
      // Handle ask_user responses
      if (data.startsWith('ask:')) {
        const [, id, indexStr] = data.split(':');
        const pending = pendingQuestions.get(id);
        
        if (pending) {
          const keyboard = (ctx.callbackQuery.message as any)?.reply_markup?.inline_keyboard;
          const optionIndex = parseInt(indexStr);
          const selectedText = keyboard?.[optionIndex]?.[0]?.text || `Option ${optionIndex + 1}`;
          
          pending.resolve(selectedText);
          
          try {
            await ctx.editMessageText(`✅ Selected: <b>${escapeHtml(selectedText)}</b>`, { parse_mode: 'HTML' });
          } catch {}
          
          await ctx.answerCbQuery(`Selected: ${selectedText}`).catch(() => {});
        } else {
          await ctx.answerCbQuery('This question has expired').catch(() => {});
        }
        return;
      }
      
      // Handle approval/deny
      const [action, id] = data.split(':');
      if (!id || (action !== 'approve' && action !== 'deny')) return;
      
      const approved = action === 'approve';
      const handled = handleApproval(id, approved);
      
      if (handled) {
        const statusText = approved 
          ? '✅ <b>Command Approved</b>' 
          : '❌ <b>Command Denied</b>';
        
        try {
          await ctx.editMessageText(statusText, { parse_mode: 'HTML' });
        } catch {}
        
        await ctx.answerCbQuery(approved ? 'Command approved' : 'Command denied').catch(() => {});
      } else {
        await ctx.answerCbQuery('This approval has expired or was already handled').catch(() => {});
      }
    } catch (e) {
      console.error('[callback] Error handling callback query:', e);
    }
  });
  
  // Check if should respond (groups: only @mention or reply)
  function shouldRespond(ctx: Context & { message?: any }): { respond: boolean; text: string } {
    const msg = ctx.message;
    if (!msg?.text) return { respond: false, text: '' };
    
    const chatType = msg.chat?.type;
    const isPrivate = chatType === 'private';
    const isGroup = chatType === 'group' || chatType === 'supergroup';
    
    // Private chat - always respond
    if (isPrivate) {
      return { respond: true, text: msg.text };
    }
    
    // Group chat - only respond to @mention or reply to bot
    if (isGroup && botUsername) {
      const replyToBot = msg.reply_to_message?.from?.username === botUsername;
      const mentionsBot = msg.text.includes(`@${botUsername}`);
      
      if (replyToBot || mentionsBot) {
        // Remove @mention from text
        const cleanText = msg.text.replace(new RegExp(`@${botUsername}\\s*`, 'gi'), '').trim();
        return { respond: true, text: cleanText || msg.text };
      }
      
      // Group message without mention/reply - ignore
      return { respond: false, text: '' };
    }
    
    return { respond: false, text: '' };
  }
  
  // Auth middleware
  bot.use(async (ctx, next) => {
    const userId = ctx.from?.id;
    if (!userId) return;
    
    if (config.allowedUsers?.length && !config.allowedUsers.includes(userId)) {
      const chatType = (ctx.message as any)?.chat?.type;
      if (chatType === 'private') {
        return ctx.reply('🚫 Access denied');
      }
      return;
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
      `/approvals - Pending approvals`;
    await ctx.reply(msg, { parse_mode: 'HTML' });
  });
  
  // /clear
  bot.command('clear', async (ctx) => {
    const id = ctx.from?.id?.toString();
    if (id) {
      cancelSessionApprovals(id);
      agent.clear(id);
      await ctx.reply('🗑 Session cleared');
    }
  });
  
  // /status
  bot.command('status', async (ctx) => {
    const id = ctx.from?.id?.toString();
    if (!id) return;
    
    const info = agent.getInfo(id);
    const pending = getSessionApprovals(id);
    const msg = `<b>📊 Status</b>\n` +
      `Model: <code>${config.model}</code>\n` +
      `History: ${info.messages} msgs\n` +
      `Tools: ${info.tools}\n` +
      `🛡️ Exec Approvals: ${pending.length} pending`;
    await ctx.reply(msg, { parse_mode: 'HTML' });
  });
  
  // /approvals - show pending approvals
  bot.command('approvals', async (ctx) => {
    const id = ctx.from?.id?.toString();
    if (!id) return;
    
    const pending = getSessionApprovals(id);
    if (pending.length === 0) {
      await ctx.reply('✅ No pending approvals');
      return;
    }
    
    for (const approval of pending) {
      const message = `⏳ <b>Pending Approval</b>\n\n` +
        `<b>Reason:</b> ${escapeHtml(approval.reason)}\n\n` +
        `<pre>${escapeHtml(approval.command)}</pre>`;
      
      await ctx.reply(message, {
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [[
            { text: '✅ Approve', callback_data: `approve:${approval.id}` },
            { text: '❌ Deny', callback_data: `deny:${approval.id}` },
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
    
    // Save chat ID for approval requests
    sessionChats.set(sessionId, ctx.chat.id);
    
    console.log(`[bot] ${userId}: ${text.slice(0, 50)}...`);
    
    await ctx.sendChatAction('typing');
    const typing = setInterval(() => ctx.sendChatAction('typing').catch(() => {}), 4000);
    
    // Status message with traces
    let statusMsg: any = null;
    const traces: string[] = [];
    
    try {
      const response = await agent.run(sessionId, text, async (toolName) => {
        const emoji = toolEmoji(toolName);
        traces.push(`${emoji} ${toolName}`);
        
        const statusText = `<b>Working...</b>\n\n${traces.join('\n')}`;
        
        try {
          if (statusMsg) {
            await ctx.telegram.editMessageText(
              ctx.chat.id, 
              statusMsg.message_id, 
              undefined, 
              statusText, 
              { parse_mode: 'HTML' }
            );
          } else {
            // Reply to user's message
            statusMsg = await ctx.reply(statusText, { 
              parse_mode: 'HTML',
              reply_parameters: { message_id: messageId }
            });
          }
        } catch {}
      });
      
      clearInterval(typing);
      
      // Delete status message
      if (statusMsg) {
        try { 
          await ctx.telegram.deleteMessage(ctx.chat.id, statusMsg.message_id); 
        } catch {}
      }
      
      // Send response as reply to user
      const finalResponse = response || '(no response from model)';
      const html = mdToHtml(finalResponse);
      const parts = splitMessage(html);
      
      for (let i = 0; i < parts.length; i++) {
        try {
          await ctx.reply(parts[i], { 
            parse_mode: 'HTML',
            reply_parameters: i === 0 ? { message_id: messageId } : undefined
          });
        } catch {
          // Fallback to plain text
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
