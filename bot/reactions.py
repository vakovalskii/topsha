"""Emoji reactions handling"""

import re
import random
import asyncio
import aiohttp

from config import CONFIG, PROXY_URL, MODEL, ALL_REACTIONS, DONE_EMOJIS


last_reaction_time = 0.0


def should_react(text: str) -> bool:
    """Decide if should add reaction to message"""
    global last_reaction_time
    now = asyncio.get_event_loop().time()
    
    if now - last_reaction_time < CONFIG.reaction_min_interval:
        return False
    
    # Remove URLs
    text_clean = re.sub(r'https?://\S+', '', text).strip()
    if len(text_clean) < CONFIG.reaction_min_text_length:
        return False
    
    if random.random() < CONFIG.reaction_chance:
        last_reaction_time = now
        return True
    return False


async def get_smart_reaction(text: str, username: str) -> str:
    """Get reaction using LLM or random"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{PROXY_URL}/v1/chat/completions",
                json={
                    "model": MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"Выбери эмодзи-реакцию. Отвечай ТОЛЬКО одним эмодзи из: {' '.join(ALL_REACTIONS)}"
                        },
                        {"role": "user", "content": f"@{username}: {text[:200]}"}
                    ],
                    "max_tokens": 10,
                    "temperature": 0.9
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content")
                    if content:
                        emoji = content.strip()
                        if emoji in ALL_REACTIONS:
                            return emoji
                        for r in ALL_REACTIONS:
                            if r in emoji:
                                return r
    except:
        pass
    
    return random.choice(ALL_REACTIONS)


def get_random_done_emoji() -> str:
    """Get random 'done' emoji"""
    return random.choice(DONE_EMOJIS)
