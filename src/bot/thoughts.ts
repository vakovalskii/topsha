/**
 * Autonomous thoughts and messages
 * 
 * Reads recent chat history and generates contextual messages via LLM
 */

import { Telegraf } from 'telegraf';
import { readFileSync, existsSync } from 'fs';
import OpenAI from 'openai';
import { saveChatMessage } from '../tools/index.js';
import { CONFIG } from '../config.js';

// Track main group chat for autonomous messages
let mainGroupChatId: number | null = null;

// OpenAI client (set from outside)
let openaiClient: OpenAI | null = null;

export function setMainGroupChatId(chatId: number) {
  mainGroupChatId = chatId;
}

export function getMainGroupChatId(): number | null {
  return mainGroupChatId;
}

export function setOpenAIClient(client: OpenAI) {
  openaiClient = client;
}

/**
 * Read recent chat history from GLOBAL_LOG.md
 */
function getRecentChatHistory(maxLines = 50): string {
  const logPath = '/workspace/_shared/GLOBAL_LOG.md';
  
  if (!existsSync(logPath)) {
    return '(пока нет истории)';
  }
  
  try {
    const content = readFileSync(logPath, 'utf-8');
    const lines = content.trim().split('\n');
    
    // Get last N lines
    const recent = lines.slice(-maxLines).join('\n');
    return recent || '(пустая история)';
  } catch (e) {
    return '(не удалось прочитать историю)';
  }
}

/**
 * Generate a contextual thought using LLM
 */
async function generateThought(): Promise<string | null> {
  if (!openaiClient) {
    console.log('[thought] OpenAI client not set, using fallback');
    return null;
  }
  
  const chatHistory = getRecentChatHistory(40);
  
  const systemPrompt = `Ты бот LocalTopSH в Telegram-чате. Твоя задача — написать одно короткое сообщение (1-2 предложения) чтобы "вклиниться" в разговор или просто что-то сказать.

Правила:
- Пиши НЕ как бот, а как живой участник чата
- Можешь комментировать что обсуждали, задать вопрос, пошутить
- Если чат давно молчал — можешь пожаловаться на скуку или спросить "кто тут"
- НЕ используй эмодзи больше 1-2 штук
- НЕ предлагай помощь напрямую (ты уже бот, это и так понятно)
- НЕ здоровайся формально
- Будь немного дерзким и с юмором
- Пиши на русском
- ТОЛЬКО текст сообщения, без пояснений

Примеры хороших сообщений:
- "чет скучно стало, никто не пишет"
- "о, интересная тема была, а чем закончилось?"
- "сижу тут один, логи читаю..."
- "кстати а помните вчера кто-то спрашивал про X? разобрались?"`;

  const userPrompt = `Вот последние сообщения в чате:

${chatHistory}

Напиши одно короткое сообщение чтобы вклиниться в разговор или просто что-то сказать (если чат молчит давно — можешь пожаловаться на скуку):`;

  try {
    const response = await openaiClient.chat.completions.create({
      model: CONFIG.model || 'gpt-4o-mini',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
      max_tokens: 150,
      temperature: 0.9,
    });
    
    const thought = response.choices[0]?.message?.content?.trim();
    
    if (!thought || thought.length < 3 || thought.length > 300) {
      console.log('[thought] Invalid response from LLM, skipping');
      return null;
    }
    
    return thought;
  } catch (e: any) {
    console.log(`[thought] LLM error: ${e.message?.slice(0, 50)}`);
    return null;
  }
}

/**
 * Fallback thoughts if LLM fails
 */
const FALLBACK_THOUGHTS = [
  'чет скучно стало...',
  'народ, есть кто живой?',
  'сижу тут один',
  'эй, чем занимаетесь?',
  'подозрительно тихо...',
];

function getFallbackThought(): string {
  return FALLBACK_THOUGHTS[Math.floor(Math.random() * FALLBACK_THOUGHTS.length)];
}

/**
 * Send thought to group
 */
async function sendThought(bot: Telegraf): Promise<void> {
  if (!mainGroupChatId) {
    return;
  }
  
  // Try LLM first, fallback to random
  let thought = await generateThought();
  
  if (!thought) {
    thought = getFallbackThought();
  }
  
  try {
    await bot.telegram.sendMessage(mainGroupChatId, thought);
    saveChatMessage('LocalTopSH', thought, true, mainGroupChatId);
    console.log(`[thought] Sent: ${thought.slice(0, 50)}...`);
  } catch (e: any) {
    console.log(`[thought] Failed to send: ${e.message?.slice(0, 50)}`);
  }
}

/**
 * Start autonomous messages scheduler
 */
export function startAutonomousMessages(bot: Telegraf) {
  if (!CONFIG.thoughts.enabled) {
    console.log('[thought] Autonomous messages disabled in config');
    return;
  }
  
  const { minIntervalMin, maxIntervalMin, startDelayMin } = CONFIG.thoughts;
  
  const scheduleNext = () => {
    const delay = (minIntervalMin + Math.random() * (maxIntervalMin - minIntervalMin)) * 60 * 1000;
    
    setTimeout(async () => {
      await sendThought(bot);
      scheduleNext();
    }, delay);
  };
  
  // First thought after startDelayMin
  setTimeout(scheduleNext, startDelayMin * 60 * 1000);
  
  console.log(`[thought] Autonomous messages enabled (${minIntervalMin}-${maxIntervalMin} min interval)`);
}
