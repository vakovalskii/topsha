/**
 * Telegram Bot Interface for Localtopsh Agent
 * Allows interaction with the AI agent through Telegram
 */

import { Telegraf, Context } from 'telegraf';
import { message } from 'telegraf/filters';
import { config } from 'dotenv';
import OpenAI from 'openai';
import { ToolExecutor } from '../agent/libs/tools-executor.js';
import { getTools, generateToolsSummary } from '../agent/libs/tools-definitions.js';
import { getInitialPrompt, getSystemPrompt } from '../agent/libs/prompt-loader.js';
import { loadApiSettings, saveApiSettings } from '../agent/libs/settings-store.js';
import type { ApiSettings } from '../agent/types.js';

config();

// Configuration
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const ALLOWED_USERS = process.env.TELEGRAM_ALLOWED_USERS?.split(',').map(id => parseInt(id.trim())) || [];
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || 'dummy-key';
const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || 'http://localhost:8000/v1';
const OPENAI_MODEL = process.env.OPENAI_MODEL || 'qwen2.5-7b-instruct';
const AGENT_CWD = process.env.AGENT_CWD || process.cwd();

if (!TELEGRAM_BOT_TOKEN) {
  console.error('TELEGRAM_BOT_TOKEN is required');
  process.exit(1);
}

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: OPENAI_API_KEY,
  baseURL: OPENAI_BASE_URL,
});

// Initialize tool executor
const apiSettings: ApiSettings = {
  apiKey: OPENAI_API_KEY,
  baseUrl: OPENAI_BASE_URL,
  model: OPENAI_MODEL,
  permissionMode: 'default', // Auto-approve in Telegram mode
  enableMemory: true,
};
const toolExecutor = new ToolExecutor(AGENT_CWD, apiSettings);

// Get available tools
const tools = getTools(apiSettings);
const toolsSummary = generateToolsSummary(tools);

// Session storage (in-memory, per user)
interface UserSession {
  messages: Array<{ role: 'system' | 'user' | 'assistant' | 'tool'; content: any; tool_calls?: any[]; tool_call_id?: string; name?: string }>;
  lastActivity: number;
}
const sessions = new Map<number, UserSession>();

// Get or create session for user
function getSession(userId: number): UserSession {
  let session = sessions.get(userId);
  if (!session) {
    const systemPrompt = getSystemPrompt(AGENT_CWD, toolsSummary);
    session = {
      messages: [{ role: 'system', content: systemPrompt }],
      lastActivity: Date.now(),
    };
    sessions.set(userId, session);
  }
  session.lastActivity = Date.now();
  return session;
}

// Clear session
function clearSession(userId: number): void {
  sessions.delete(userId);
}

// Check if user is allowed
function isAllowedUser(userId: number): boolean {
  if (ALLOWED_USERS.length === 0) return true; // No restrictions if list is empty
  return ALLOWED_USERS.includes(userId);
}

// Create bot
const bot = new Telegraf(TELEGRAM_BOT_TOKEN);

// Middleware: Check allowed users
bot.use(async (ctx, next) => {
  const userId = ctx.from?.id;
  if (!userId || !isAllowedUser(userId)) {
    await ctx.reply('⛔ Access denied. Your user ID is not in the allowed list.');
    console.log(`[Telegram] Denied access for user ${userId}`);
    return;
  }
  return next();
});

// Command: /start
bot.command('start', async (ctx) => {
  const userId = ctx.from?.id;
  if (!userId) return;
  
  clearSession(userId);
  await ctx.reply(
    '🤖 *Localtopsh Agent*\n\n' +
    'I am an autonomous AI agent with access to various tools:\n' +
    '• File operations (read, write, edit)\n' +
    '• Web search\n' +
    '• Code execution (Python, JavaScript)\n' +
    '• Browser automation\n' +
    '• Git operations\n\n' +
    '*Commands:*\n' +
    '/clear - Clear conversation history\n' +
    '/status - Show agent status\n' +
    '/help - Show help\n\n' +
    'Just send me a message to start!',
    { parse_mode: 'Markdown' }
  );
});

// Command: /clear
bot.command('clear', async (ctx) => {
  const userId = ctx.from?.id;
  if (!userId) return;
  
  clearSession(userId);
  await ctx.reply('🗑️ Conversation cleared. Starting fresh!');
});

// Command: /status
bot.command('status', async (ctx) => {
  const userId = ctx.from?.id;
  if (!userId) return;
  
  const session = sessions.get(userId);
  const messageCount = session ? session.messages.length - 1 : 0; // Exclude system message
  
  await ctx.reply(
    `📊 *Agent Status*\n\n` +
    `Model: \`${OPENAI_MODEL}\`\n` +
    `Base URL: \`${OPENAI_BASE_URL}\`\n` +
    `Working Dir: \`${AGENT_CWD}\`\n` +
    `Messages in session: ${messageCount}\n` +
    `Available tools: ${tools.length}`,
    { parse_mode: 'Markdown' }
  );
});

// Command: /help
bot.command('help', async (ctx) => {
  await ctx.reply(
    '📖 *Help*\n\n' +
    '*Available Tools:*\n' +
    tools.map(t => `• \`${t.function.name}\``).join('\n') + '\n\n' +
    '*Tips:*\n' +
    '• I can read and write files in the workspace\n' +
    '• I can search the web for information\n' +
    '• I can execute Python and JavaScript code\n' +
    '• I can automate browser tasks\n' +
    '• I can work with Git repositories\n\n' +
    'Just describe what you need!',
    { parse_mode: 'Markdown' }
  );
});

// Handle text messages
bot.on(message('text'), async (ctx) => {
  const userId = ctx.from?.id;
  if (!userId) return;
  
  const userMessage = ctx.message.text;
  const session = getSession(userId);
  
  // Add user message to session
  const formattedPrompt = getInitialPrompt(userMessage);
  session.messages.push({ role: 'user', content: formattedPrompt });
  
  // Send typing indicator
  await ctx.sendChatAction('typing');
  
  try {
    // Run agent loop
    const MAX_ITERATIONS = 20;
    let iteration = 0;
    
    while (iteration < MAX_ITERATIONS) {
      iteration++;
      
      // Keep typing indicator active
      const typingInterval = setInterval(() => {
        ctx.sendChatAction('typing').catch(() => {});
      }, 4000);
      
      try {
        // Call LLM
        const response = await openai.chat.completions.create({
          model: OPENAI_MODEL,
          messages: session.messages as any[],
          tools: tools as any[],
          stream: false,
        });
        
        const choice = response.choices[0];
        const assistantMessage = choice.message;
        
        // Add assistant message to session
        session.messages.push({
          role: 'assistant',
          content: assistantMessage.content || '',
          tool_calls: assistantMessage.tool_calls,
        });
        
        // If no tool calls, send response and done
        if (!assistantMessage.tool_calls || assistantMessage.tool_calls.length === 0) {
          clearInterval(typingInterval);
          
          if (assistantMessage.content) {
            // Split long messages
            const maxLength = 4000;
            const content = assistantMessage.content;
            
            if (content.length <= maxLength) {
              await ctx.reply(content, { parse_mode: 'Markdown' }).catch(() => 
                ctx.reply(content) // Retry without markdown if fails
              );
            } else {
              // Split into chunks
              for (let i = 0; i < content.length; i += maxLength) {
                const chunk = content.slice(i, i + maxLength);
                await ctx.reply(chunk);
              }
            }
          }
          break;
        }
        
        // Execute tools
        for (const toolCall of assistantMessage.tool_calls) {
          const toolName = toolCall.function.name;
          const toolArgs = JSON.parse(toolCall.function.arguments || '{}');
          
          console.log(`[Telegram] Executing tool: ${toolName}`, toolArgs);
          
          // Notify user about tool execution
          await ctx.reply(`⚙️ \`${toolName}\`...`, { parse_mode: 'Markdown' });
          
          // Execute tool
          const result = await toolExecutor.executeTool(toolName, toolArgs, {
            sessionId: `tg-${userId}`,
          });
          
          // Add tool result to session
          session.messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            name: toolName,
            content: result.success ? (result.output || 'Success') : `Error: ${result.error}`,
          });
          
          // Notify about result (abbreviated)
          const resultPreview = result.success 
            ? (result.output?.substring(0, 200) + (result.output && result.output.length > 200 ? '...' : '') || 'Success')
            : `Error: ${result.error}`;
          
          console.log(`[Telegram] Tool result: ${resultPreview}`);
        }
        
        clearInterval(typingInterval);
        
      } catch (error) {
        clearInterval(typingInterval);
        throw error;
      }
    }
    
    if (iteration >= MAX_ITERATIONS) {
      await ctx.reply('⚠️ Max iterations reached. Task may be incomplete.');
    }
    
  } catch (error: any) {
    console.error('[Telegram] Error:', error);
    await ctx.reply(`❌ Error: ${error.message || 'Unknown error'}`);
  }
});

// Handle photos (for image analysis)
bot.on(message('photo'), async (ctx) => {
  await ctx.reply('📸 Image analysis is not yet implemented. Please send text messages.');
});

// Handle documents
bot.on(message('document'), async (ctx) => {
  await ctx.reply('📄 Document handling is not yet implemented. Please send text messages.');
});

// Error handling
bot.catch((err: any, ctx: Context) => {
  console.error('[Telegram] Bot error:', err);
  ctx.reply('❌ An error occurred. Please try again.').catch(() => {});
});

// Start bot
console.log('🚀 Starting Localtopsh Telegram Bot...');
console.log(`📍 Working directory: ${AGENT_CWD}`);
console.log(`🤖 Model: ${OPENAI_MODEL}`);
console.log(`🌐 API URL: ${OPENAI_BASE_URL}`);
console.log(`👥 Allowed users: ${ALLOWED_USERS.length === 0 ? 'Everyone' : ALLOWED_USERS.join(', ')}`);

bot.launch();

// Graceful shutdown
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
