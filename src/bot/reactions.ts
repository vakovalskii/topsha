/**
 * Emoji reactions and LLM-based reaction selection
 */

import OpenAI from 'openai';
import { CONFIG, getAllReactions } from '../config.js';

// Use reactions from config
export const POSITIVE_REACTIONS = CONFIG.allReactions.positive;
export const NEGATIVE_REACTIONS = CONFIG.allReactions.negative;
export const NEUTRAL_REACTIONS = CONFIG.allReactions.neutral;

// All available reactions (from config)
// Removed: 💀 😂 (REACTION_INVALID - tested 2026-02-03)
export const ALL_REACTIONS = getAllReactions();

export function getRandomReaction(sentiment: 'positive' | 'negative' | 'neutral' | 'random'): string {
  let pool: string[];
  const weights = CONFIG.reactions.weights;
  
  if (sentiment === 'random') {
    // Weighted random from config
    const rand = Math.random();
    if (rand < weights.positive) pool = POSITIVE_REACTIONS;
    else if (rand < weights.positive + weights.neutral) pool = NEUTRAL_REACTIONS;
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

// LLM client for reactions (will be set in createBot)
let reactionLLM: OpenAI | null = null;
let reactionModel = '';

export function initReactionLLM(client: OpenAI, model: string) {
  reactionLLM = client;
  reactionModel = model;
}

// Get reaction via LLM
export async function getSmartReaction(text: string, username: string): Promise<string> {
  if (!reactionLLM) {
    // Fallback to random
    return ALL_REACTIONS[Math.floor(Math.random() * ALL_REACTIONS.length)];
  }
  
  try {
    const response = await reactionLLM.chat.completions.create({
      model: reactionModel,
      messages: [
        {
          role: 'system',
          content: `Ты выбираешь эмодзи-реакцию на сообщение в чате. Отвечай ТОЛЬКО одним эмодзи из списка.
Доступные: ${ALL_REACTIONS.join(' ')}

ПРАВИЛА:
- Смешное/ироничное → 😂🤣😈
- Крутое/полезное/интересное → 🔥💯🏆👏❤️👍
- Вопрос/размышление → 🤔👀
- Милое/доброе → 😍🤗❤️
- Грустное → 💔

ВАЖНО: 
- НЕ ставь негативные реакции (💩🤡🗿😴🤮) на нейтральные сообщения!
- 🤡💩 только если человек ЯВНО написал глупость или бред
- При сомнении используй нейтральные: 👀🤔👍

Отвечай ОДНИМ эмодзи!`
        },
        {
          role: 'user',
          content: `@${username}: ${text.slice(0, 200)}`
        }
      ],
      max_tokens: CONFIG.reactions.llmMaxTokens,
      temperature: 0.9,
    });
    
    const emoji = response.choices[0]?.message?.content?.trim() || '';
    
    // Validate it's a real emoji from our list
    if (ALL_REACTIONS.includes(emoji)) {
      return emoji;
    }
    
    // Try to extract emoji from response
    for (const r of ALL_REACTIONS) {
      if (emoji.includes(r)) return r;
    }
    
    // Fallback
    return ALL_REACTIONS[Math.floor(Math.random() * ALL_REACTIONS.length)];
  } catch (e: any) {
    console.log(`[reaction] LLM error: ${e.message?.slice(0, 50)}`);
    return ALL_REACTIONS[Math.floor(Math.random() * ALL_REACTIONS.length)];
  }
}

// Rate limit for reactions
let lastReactionTime = 0;

// Should we react to this message?
export function shouldReact(text: string): boolean {
  const now = Date.now();
  // Rate limit from config
  if (now - lastReactionTime < CONFIG.reactions.minInterval) {
    return false;
  }
  
  // Skip messages that are mostly links
  const linkPattern = /https?:\/\/\S+/g;
  const textWithoutLinks = text.replace(linkPattern, '').trim();
  if (textWithoutLinks.length < CONFIG.reactions.minTextLength) {
    return false; // Message is mostly a link
  }
  
  // Skip very short messages
  if (text.length < 5) {
    return false;
  }
  
  // React based on chance from config
  if (Math.random() < CONFIG.reactions.randomChance) {
    lastReactionTime = now;
    return true;
  }
  return false;
}
