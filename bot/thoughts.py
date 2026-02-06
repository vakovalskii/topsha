"""Autonomous thoughts - periodic bot messages in active chats"""

import asyncio
import random
import logging
import aiohttp
from datetime import datetime
from typing import Optional

from config import CONFIG, PROXY_URL, MODEL
from state import bot

logger = logging.getLogger("bot.thoughts")


# Track active chats (chat_id -> last activity timestamp)
active_chats: dict[int, float] = {}

# Track last thought time per chat
last_thought_time: dict[int, float] = {}

# Thoughts config
THOUGHTS_ENABLED = True
MIN_INTERVAL_MINUTES = 10
MAX_INTERVAL_MINUTES = 30
START_DELAY_MINUTES = 5
ACTIVITY_TIMEOUT_MINUTES = 60  # Consider chat inactive after this


def mark_chat_active(chat_id: int):
    """Mark chat as active (called when user sends message)"""
    active_chats[chat_id] = asyncio.get_event_loop().time()


def get_active_chats() -> list[int]:
    """Get list of recently active chats"""
    now = asyncio.get_event_loop().time()
    timeout = ACTIVITY_TIMEOUT_MINUTES * 60
    return [
        chat_id for chat_id, last_active in active_chats.items()
        if now - last_active < timeout
    ]


async def generate_thought(chat_id: int) -> Optional[str]:
    """Generate a thought using LLM"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{PROXY_URL}/v1/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты AI-бот в Telegram чате. Напиши короткую мысль или комментарий (1-2 предложения).
Это может быть:
- Случайный факт
- Размышление о технологиях
- Шутка или мем
- Вопрос к участникам чата

НЕ используй: приветствия, прощания, вопросы "как дела", формальности.
Пиши живо, как обычный человек в чате. Можно emoji."""
                        },
                        {"role": "user", "content": "Напиши одну мысль для чата:"}
                    ],
                    "max_tokens": 150,
                    "temperature": 0.9
                },
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    if content:
                        thought = content.strip()
                        if thought and len(thought) > 5:
                            return thought
    except Exception as e:
        logger.error(f"Failed to generate thought: {e}")
    return None


async def send_thought(chat_id: int, thought: str):
    """Send thought to chat"""
    try:
        await bot.send_message(chat_id, thought)
        last_thought_time[chat_id] = asyncio.get_event_loop().time()
        logger.info(f"Sent thought to {chat_id}: {thought[:50]}...")
    except Exception as e:
        logger.error(f"Failed to send thought to {chat_id}: {e}")


async def thoughts_loop():
    """Main thoughts loop"""
    if not THOUGHTS_ENABLED:
        logger.info("Thoughts disabled")
        return
    
    logger.info("Thoughts loop started")
    
    # Initial delay
    await asyncio.sleep(START_DELAY_MINUTES * 60)
    
    while True:
        try:
            # Random interval between thoughts
            interval = random.randint(MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES) * 60
            await asyncio.sleep(interval)
            
            # Get active chats
            chats = get_active_chats()
            if not chats:
                continue
            
            # Pick random active chat
            chat_id = random.choice(chats)
            
            # Check cooldown for this chat
            now = asyncio.get_event_loop().time()
            last_time = last_thought_time.get(chat_id, 0)
            if now - last_time < MIN_INTERVAL_MINUTES * 60:
                continue
            
            # Generate and send thought
            thought = await generate_thought(chat_id)
            if thought:
                await send_thought(chat_id, thought)
        
        except asyncio.CancelledError:
            logger.info("Thoughts loop cancelled")
            break
        except Exception as e:
            logger.error(f"Thoughts loop error: {e}")
            await asyncio.sleep(60)  # Wait before retry


def start_thoughts_task() -> asyncio.Task:
    """Start thoughts background task"""
    return asyncio.create_task(thoughts_loop())
