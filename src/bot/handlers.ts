/**
 * Telegram callback handlers (approval, ask_user, etc.)
 */

import { Telegraf, Context } from 'telegraf';
import { escapeHtml } from './formatters.js';
import { executeCommand } from '../tools/bash.js';
import { 
  consumePendingCommand, 
  cancelPendingCommand,
} from '../approvals/index.js';
import type { PendingQuestion } from './types.js';
import { CONFIG } from '../config.js';

// Pending questions storage
export const pendingQuestions = new Map<string, PendingQuestion>();

// Handle EXECUTE button - runs the command
export function setupExecuteHandler(bot: Telegraf) {
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
      const result = await executeCommand(pending.command, pending.cwd);
      
      // Show result
      const output = result.success 
        ? (result.output || '(empty output)')
        : `Error: ${result.error}`;
      
      const trimmedOutput = output.length > CONFIG.messages.outputTrimLength 
        ? output.slice(0, CONFIG.messages.outputHeadLength) + '\n...\n' + output.slice(-CONFIG.messages.outputTailLength)
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
}

// Handle DENY button
export function setupDenyHandler(bot: Telegraf) {
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
}

// Handle ask_user buttons
export function setupAskHandler(bot: Telegraf) {
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
}

// Setup all callback handlers
export function setupAllHandlers(bot: Telegraf) {
  setupExecuteHandler(bot);
  setupDenyHandler(bot);
  setupAskHandler(bot);
}
