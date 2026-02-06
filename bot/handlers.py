"""Message handlers and commands"""

import re
import random
import asyncio
import traceback

from aiogram import types, F
from aiogram.types import Message, ReactionTypeEmoji
from aiogram.filters import Command
from aiogram.enums import ChatType

from config import (
    CONFIG, CORE_URL, MODEL, ADMIN_USER_ID,
    USERBOT_ID, MAX_BOT_REPLIES, BOT_COOLDOWN
)
from state import (
    bot, dp, bot_username, bot_id,
    is_afk, set_afk, clear_afk,
    bot_conversation_count, bot_conversation_reset
)
from formatters import md_to_html, split_message, clean_model_artifacts
from rate_limiter import rate_limiter
from reactions import should_react, get_smart_reaction, get_random_done_emoji
from security import detect_prompt_injection
from api import call_core, clear_session
from thoughts import mark_chat_active


def should_respond(message: Message) -> tuple[bool, str, bool]:
    """Check if bot should respond. Returns (should_respond, text, is_random)"""
    if not message.text:
        return False, "", False
    
    chat_type = message.chat.type
    is_private = chat_type == ChatType.PRIVATE
    is_group = chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)
    
    if is_private:
        return True, message.text, False
    
    if is_group:
        from state import bot_id, bot_username
        reply = message.reply_to_message
        reply_to_bot = reply and (reply.from_user.id == bot_id or reply.from_user.username == bot_username)
        mentions_bot = bot_username and f"@{bot_username}" in message.text
        
        if reply_to_bot or mentions_bot:
            clean_text = message.text
            if bot_username:
                clean_text = re.sub(f"@{bot_username}\\s*", "", clean_text, flags=re.IGNORECASE).strip()
            return True, clean_text or message.text, False
        
        if random.random() < CONFIG.random_reply_chance and len(message.text) > CONFIG.min_text_for_random:
            return True, message.text, True
    
    return False, "", False


async def set_reaction(chat_id: int, message_id: int, emoji: str):
    """Set reaction on message"""
    try:
        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)]
        )
    except:
        pass


# ============ COMMANDS ============

@dp.message(Command("start"))
async def cmd_start(message: Message):
    from state import bot_username
    chat_type = message.chat.type
    group_hint = f"💬 In groups: @{bot_username} or reply\n\n" if chat_type != ChatType.PRIVATE else ""
    await message.reply(
        f"<b>🤖 Coding Agent</b>\n\n"
        f"{group_hint}"
        f"/clear - Reset session\n/status - Status"
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    if await clear_session(user_id):
        await message.reply("🗑 Session cleared")
    else:
        await message.reply("❌ Failed to clear session")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    await message.reply(
        f"<b>📊 Status</b>\n"
        f"Model: <code>{MODEL}</code>\n"
        f"Core: <code>{CORE_URL}</code>"
    )


@dp.message(Command("afk"))
async def cmd_afk(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_USER_ID:
        await message.reply("Только хозяин может меня отправить по делам 😏")
        return
    
    args = message.text.split()[1:] if message.text else []
    minutes = int(args[0]) if args and args[0].isdigit() else CONFIG.afk_default_minutes
    reason = " ".join(args[1:]) if len(args) > 1 else "ушёл по делам"
    
    if minutes <= 0:
        clear_afk()
        await message.reply("Я вернулся! 🎉")
        return
    
    minutes = min(minutes, CONFIG.afk_max_minutes)
    set_afk(minutes, reason)
    await message.reply(f"Ладно, {reason}. Буду через {minutes} мин ✌️")


# ============ MESSAGE HANDLER ============

@dp.message(F.text)
async def handle_message(message: Message):
    from state import bot_id
    
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return
    
    chat_type = message.chat.type
    is_group = chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)
    chat_id = message.chat.id
    message_id = message.message_id
    
    # React in groups
    if is_group and message.text and message.from_user.id != bot_id:
        if should_react(message.text):
            username = message.from_user.username or message.from_user.first_name or "anon"
            reaction = await get_smart_reaction(message.text, username)
            await set_reaction(chat_id, message_id, reaction)
    
    # AFK mode
    if is_afk():
        await set_reaction(chat_id, message_id, "💤")
        return
    
    # Check if should respond
    respond, text, is_random = should_respond(message)
    if not respond or not text:
        return
    
    is_private = chat_type == ChatType.PRIVATE
    
    # Anti-loop: limit bot-to-bot conversation
    if user_id == USERBOT_ID and is_group:
        key = (chat_id, user_id)
        now = asyncio.get_event_loop().time()
        
        last_reset = bot_conversation_reset.get(key, 0)
        if now - last_reset > BOT_COOLDOWN:
            bot_conversation_count[key] = 0
            bot_conversation_reset[key] = now
        
        count = bot_conversation_count.get(key, 0)
        if count >= MAX_BOT_REPLIES:
            print(f"[anti-loop] Ignoring userbot in {chat_id} (count={count})")
            return
        
        bot_conversation_count[key] = count + 1
    
    # Random ignore
    ignore_chance = CONFIG.ignore_private_chance if is_private else CONFIG.ignore_chance
    if not is_random and random.random() < ignore_chance:
        if random.random() < 0.5:
            ignore_emojis = ["😴", "🙈", "💤", "🤷"]
            await set_reaction(chat_id, message_id, random.choice(ignore_emojis))
        return
    
    username = message.from_user.username or message.from_user.first_name or str(user_id)
    
    # Check if this is answer to pending question
    from server import check_pending_answer
    if check_pending_answer(user_id, chat_id, text):
        await set_reaction(chat_id, message_id, "✅")
        return
    
    # Format message for agent
    if is_random:
        message_for_agent = f"[От: @{username} ({user_id})]\n[Случайный комментарий]\n\n{text}"
    else:
        message_for_agent = f"[От: @{username} ({user_id})]\n{text}"
    
    # Check concurrent users limit
    if not rate_limiter.can_accept_user(user_id):
        await set_reaction(chat_id, message_id, "🤔")
        await rate_limiter.safe_send(
            chat_id,
            message.reply("⏳ Сервер занят, попробуй через минуту")
        )
        return
    
    print(f"\n[IN] @{username} ({user_id}):\n{text}\n")
    
    # Mark chat as active for autonomous thoughts
    mark_chat_active(chat_id)
    
    # Prompt injection detection
    if detect_prompt_injection(text):
        print(f"[SECURITY] Prompt injection from {user_id}")
        await set_reaction(chat_id, message_id, "🤨")
        await rate_limiter.safe_send(chat_id, message.reply("Хорошая попытка 😏"))
        return
    
    # React with 👀
    await set_reaction(chat_id, message_id, "👀")
    
    rate_limiter.mark_active(user_id)
    
    # Process with user lock
    async with rate_limiter.get_user_lock(user_id):
        typing_task = None
        try:
            # Typing indicator
            async def typing_loop():
                while True:
                    try:
                        await bot.send_chat_action(chat_id, "typing")
                    except:
                        pass
                    await asyncio.sleep(CONFIG.typing_interval)
            
            typing_task = asyncio.create_task(typing_loop())
            
            # Small delay
            delay = CONFIG.think_delay_min + random.random() * (CONFIG.think_delay_max - CONFIG.think_delay_min)
            await asyncio.sleep(delay)
            
            # Call core
            chat_type_str = chat_type.value if hasattr(chat_type, 'value') else str(chat_type)
            core_result = await call_core(user_id, chat_id, message_for_agent, username, chat_type_str)
            
            # Stop typing
            if typing_task:
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
            
            # Check if bot is disabled
            if core_result.disabled:
                await set_reaction(chat_id, message_id, "🔒")
                return
            
            # Check if access denied
            if core_result.access_denied:
                await set_reaction(chat_id, message_id, "🚫")
                return
            
            # Done reaction
            await set_reaction(chat_id, message_id, get_random_done_emoji())
            
            # Send response
            final_response = core_result.response or "(no response)"
            final_response = clean_model_artifacts(final_response)
            print(f"[OUT] → @{username}:\n{final_response[:200]}\n")
            
            html_response = md_to_html(final_response)
            parts = split_message(html_response, CONFIG.max_length)
            
            for i, part in enumerate(parts):
                sent = await rate_limiter.safe_send(
                    chat_id,
                    message.reply(part) if i == 0 else bot.send_message(chat_id, part)
                )
                
                if not sent and i == 0:
                    # Fallback to plain text
                    import re
                    plain = re.sub(r'<[^>]+>', '', part)[:4000]
                    await rate_limiter.safe_send(chat_id, message.reply(plain))
                    break
        
        except Exception as e:
            if typing_task:
                typing_task.cancel()
            
            print(f"[bot] Error: {e}")
            traceback.print_exc()
            await set_reaction(chat_id, message_id, "👎")
            await rate_limiter.safe_send(chat_id, message.reply(f"❌ Error: {str(e)[:200]}"))
        
        finally:
            rate_limiter.mark_inactive(user_id)
