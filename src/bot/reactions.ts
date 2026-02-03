/**
 * Emoji reactions and LLM-based reaction selection
 */

import OpenAI from 'openai';

// Random reactions for messages (only Telegram-allowed emojis!)
// Full list: 👍👎❤️🔥🥰👏😁🤔🤯😱🤬😢🎉🤩🤮💩🙏👌🕊🤡🥱🥴😍🐳❤️‍🔥🌚🌭💯🤣⚡🍌🏆💔🤨😐🍓🍾💋🖕😈😴😭🤓👻👨‍💻👀🎃🙈😇😨🤝✍️🤗🫡🎅🎄☃️💅🤪🗿🆒💘🙉🦄😘💊🙊😎👾🤷‍♂️🤷🤷‍♀️😡
export const POSITIVE_REACTIONS = ['❤️', '🔥', '👍', '🎉', '💯', '🤩', '👏', '😍', '🤗', '🏆'];
export const NEGATIVE_REACTIONS = ['💩', '👎', '🤡', '😴', '🥱', '🗿', '🤮', '💔', '😡'];
export const NEUTRAL_REACTIONS = ['👀', '🤔', '🤨', '😐', '🌚', '👻', '🤷'];

// All available reactions for LLM to choose from
export const ALL_REACTIONS = ['❤️', '🔥', '👍', '🎉', '💯', '🤩', '👏', '😍', '🤗', '🏆', '💩', '👎', '🤡', '😴', '🥱', '🗿', '🤮', '💔', '😡', '👀', '🤔', '🤨', '😐', '🌚', '👻', '🤷', '😂', '🤣', '😈', '🙈', '🎃', '💀', '🤯'];

export function getRandomReaction(sentiment: 'positive' | 'negative' | 'neutral' | 'random'): string {
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
      max_tokens: 10,
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
const MIN_REACTION_INTERVAL = 5000; // 5 seconds between reactions

// Should we react to this message?
export function shouldReact(text: string): boolean {
  const now = Date.now();
  // Rate limit: at least 5 seconds between reactions
  if (now - lastReactionTime < MIN_REACTION_INTERVAL) {
    return false;
  }
  
  // Skip messages that are mostly links
  const linkPattern = /https?:\/\/\S+/g;
  const textWithoutLinks = text.replace(linkPattern, '').trim();
  if (textWithoutLinks.length < 10) {
    return false; // Message is mostly a link
  }
  
  // Skip very short messages
  if (text.length < 5) {
    return false;
  }
  
  // React to ~15% of messages
  if (Math.random() < 0.15) {
    lastReactionTime = now;
    return true;
  }
  return false;
}
