/**
 * Bot commands (/start, /clear, /status, /pending, /afk)
 */

import { Telegraf, Context } from 'telegraf';
import { join } from 'path';
import { ReActAgent } from '../agent/react.js';
import { toolNames, saveChatMessage } from '../tools/index.js';
import { getSessionPendingCommands } from '../approvals/index.js';
import { escapeHtml } from './formatters.js';
import type { BotConfig } from './types.js';

// AFK state
let afkUntil = 0;
let afkReason = '';

export function isAfk(): boolean {
  return afkUntil > 0 && Date.now() < afkUntil;
}

export function getAfkReason(): string {
  return afkReason;
}

export function clearAfk() {
  afkUntil = 0;
  afkReason = '';
}

export function setAfk(minutes: number, reason: string) {
  afkUntil = Date.now() + minutes * 60 * 1000;
  afkReason = reason;
}

export function getAfkUntil(): number {
  return afkUntil;
}

// Setup /start command
export function setupStartCommand(bot: Telegraf, botUsername: string) {
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
}

// Setup /clear command
export function setupClearCommand(bot: Telegraf, getAgent: (userId: number) => ReActAgent) {
  bot.command('clear', async (ctx) => {
    const userId = ctx.from?.id;
    if (userId) {
      const agent = getAgent(userId);
      agent.clear(String(userId));
      await ctx.reply('🗑 Session cleared');
    }
  });
}

// Setup /status command
export function setupStatusCommand(bot: Telegraf, config: BotConfig, getAgent: (userId: number) => ReActAgent) {
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
}

// Setup /pending command
export function setupPendingCommand(bot: Telegraf) {
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
}

// Setup /afk command (admin only)
export function setupAfkCommand(bot: Telegraf) {
  bot.command('afk', async (ctx) => {
    const userId = ctx.from?.id;
    // Only allow specific admin (VaKovaLskii)
    if (userId !== 809532582) {
      await ctx.reply('Только хозяин может меня отправить по делам 😏');
      return;
    }
    
    const args = ctx.message?.text?.split(' ').slice(1) || [];
    const minutes = parseInt(args[0]) || 5;
    const reason = args.slice(1).join(' ') || 'ушёл по делам';
    
    if (minutes <= 0) {
      // Cancel AFK
      clearAfk();
      await ctx.reply('Я вернулся! 🎉');
      return;
    }
    
    // Set AFK (max 60 min)
    const actualMinutes = Math.min(minutes, 60);
    setAfk(actualMinutes, reason);
    
    await ctx.reply(`Ладно, ${reason}. Буду через ${actualMinutes} мин ✌️`);
    saveChatMessage('LocalTopSH', `[AFK] ${reason}, вернусь через ${actualMinutes} мин`, true);
    
    // Auto-return message
    setTimeout(async () => {
      if (isAfk() && Date.now() >= getAfkUntil()) {
        clearAfk();
        try {
          await bot.telegram.sendMessage(ctx.chat.id, 'Вернулся! Что я пропустил? 👀');
          saveChatMessage('LocalTopSH', 'Вернулся! Что я пропустил? 👀', true);
        } catch {}
      }
    }, actualMinutes * 60 * 1000);
  });
}

// Setup all commands
export function setupAllCommands(
  bot: Telegraf, 
  config: BotConfig, 
  botUsername: string,
  getAgent: (userId: number) => ReActAgent
) {
  setupStartCommand(bot, botUsername);
  setupClearCommand(bot, getAgent);
  setupStatusCommand(bot, config, getAgent);
  setupPendingCommand(bot);
  setupAfkCommand(bot);
}
