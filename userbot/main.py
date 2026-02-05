"""
LocalTopSH Userbot - Telethon-based agent that runs from user account
Decides autonomously whether to respond to messages
Also exposes HTTP API for gateway to call userbot capabilities as tools
"""

import os
import re
import asyncio
import aiohttp
import random
import json
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

load_dotenv()

# ============ FASTAPI APP ============
app = FastAPI(title="Userbot API", description="Telegram userbot capabilities as HTTP API")

# Global client (initialized in main)
telegram_client: TelegramClient | None = None

def read_secret(name: str, env_key: str) -> str:
    """Read from Docker Secret or env fallback"""
    paths = [f'/run/secrets/{name}', f'/run/secrets/{name}.txt']
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    return os.getenv(env_key, '')

# ============ CONFIG ============
API_ID = int(read_secret('telegram_api_id', 'TELEGRAM_API_ID') or 0)
API_HASH = read_secret('telegram_api_hash', 'TELEGRAM_API_HASH')
PHONE = read_secret('telegram_phone', 'TELEGRAM_PHONE')
CORE_URL = os.getenv('CORE_URL', 'http://core:4000')

# Response settings (can override via env)
RESPONSE_CHANCE_DM = float(os.getenv('RESPONSE_CHANCE_DM', '0.6'))       # 60% in DMs
RESPONSE_CHANCE_GROUP = float(os.getenv('RESPONSE_CHANCE_GROUP', '0.1')) # 10% base in groups
RESPONSE_CHANCE_MENTION = float(os.getenv('RESPONSE_CHANCE_MENTION', '0.5'))  # 50% when mentioned
RESPONSE_CHANCE_REPLY = float(os.getenv('RESPONSE_CHANCE_REPLY', '0.4'))  # 40% on reply to me
COOLDOWN_SECONDS = int(os.getenv('COOLDOWN_SECONDS', '60'))  # 60s between responses
IGNORE_BOTS = True            # Don't respond to other bots
MIN_MESSAGE_LENGTH = 2        # Ignore very short messages

# Chats to monitor (empty = all chats)
ALLOWED_CHATS = []  # Add chat IDs to limit, e.g. [-1001234567890]
IGNORED_CHATS = []  # Add chat IDs to ignore

# Owner IDs (can send direct commands) - comma-separated list
_owner_ids_raw = os.getenv('OWNER_ID', '0')
OWNER_IDS = set(int(x.strip()) for x in _owner_ids_raw.split(',') if x.strip().isdigit())
OWNER_ONLY = os.getenv('OWNER_ONLY', 'true').lower() == 'true'  # Only respond to owners

# ============ WHITELIST (dynamic, persisted) ============
WHITELIST_FILE = os.path.join(os.path.dirname(__file__), 'session', 'whitelist.json')

def load_whitelist() -> dict:
    """Load whitelist from file: {user_id: username}"""
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE) as f:
                return {int(k): v for k, v in json.load(f).items()}
        except:
            pass
    return {}

def save_whitelist(whitelist: dict):
    """Save whitelist to file"""
    os.makedirs(os.path.dirname(WHITELIST_FILE), exist_ok=True)
    with open(WHITELIST_FILE, 'w') as f:
        json.dump({str(k): v for k, v in whitelist.items()}, f)

WHITELIST = load_whitelist()  # {user_id: username}

# ============ SYSTEM PROMPT ============
def load_system_prompt() -> str:
    """Load userbot's system prompt"""
    prompt_file = os.path.join(os.path.dirname(__file__), 'system.txt')
    if os.path.exists(prompt_file):
        with open(prompt_file) as f:
            return f.read()
    return ""

SYSTEM_PROMPT_TEMPLATE = load_system_prompt()

# ============ STATE ============
last_response_time = {}  # chat_id -> timestamp
my_user_id = None
my_username = None

# Anti-loop: track bot-to-bot conversations
bot_conversation_count: dict[tuple[int, int], int] = {}  # (chat_id, bot_id) -> count
bot_conversation_reset: dict[tuple[int, int], float] = {}  # (chat_id, bot_id) -> timestamp
TELEGRAM_BOT_ID = 8572582989  # @localtopshbot
MAX_BOT_REPLIES = 3  # Max replies to bot per chat before cooldown
BOT_COOLDOWN = 120  # Seconds

# ============ HELPERS ============

def should_respond(event, message_text: str) -> tuple[bool, str]:
    """
    Decide if we should respond to this message.
    Returns (should_respond, reason)
    """
    global my_user_id, my_username
    
    chat_id = event.chat_id
    sender_id = event.sender_id
    
    # Don't respond to ourselves
    if sender_id == my_user_id:
        return False, "own message"
    
    # OWNER_ONLY mode - only respond to owners or whitelisted users
    if OWNER_ONLY:
        is_owner = sender_id in OWNER_IDS
        is_whitelisted = sender_id in WHITELIST
        if not is_owner and not is_whitelisted:
            return False, "not owner/whitelisted (OWNER_ONLY mode)"
    
    # Check ignored chats
    if chat_id in IGNORED_CHATS:
        return False, "ignored chat"
    
    # Check allowed chats (if specified)
    if ALLOWED_CHATS and chat_id not in ALLOWED_CHATS:
        return False, "not in allowed chats"
    
    # Ignore very short messages
    if len(message_text.strip()) < MIN_MESSAGE_LENGTH:
        return False, "too short"
    
    # Check cooldown
    now = datetime.now()
    if chat_id in last_response_time:
        elapsed = (now - last_response_time[chat_id]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            return False, f"cooldown ({int(COOLDOWN_SECONDS - elapsed)}s left)"
    
    # Determine chat type and base chance
    is_dm = event.is_private
    is_mentioned = my_username and f"@{my_username.lower()}" in message_text.lower()
    is_reply_to_me = event.is_reply and event.reply_to_msg_id  # Will check if reply to our msg
    
    if is_dm:
        chance = RESPONSE_CHANCE_DM
        reason = "DM"
    elif is_mentioned:
        chance = RESPONSE_CHANCE_MENTION
        reason = "mentioned"
    elif is_reply_to_me:
        chance = RESPONSE_CHANCE_REPLY
        reason = "reply to me"
    else:
        # In groups: only respond to mentions/replies, not random messages
        # Even for owner - ignore plain group messages
        if OWNER_ONLY:
            return False, "group message (owner mode: only DM/reply/mention)"
        chance = RESPONSE_CHANCE_GROUP
        reason = "group message"
    
    # Keywords that increase response chance
    interesting_keywords = ['помоги', 'подскажи', 'как ', 'что ', 'почему', 'зачем', 
                           'help', 'how', 'what', 'why', 'can you', 'please',
                           'код', 'ошибка', 'error', 'bug', 'python', 'javascript']
    
    for kw in interesting_keywords:
        if kw in message_text.lower():
            chance = min(chance + 0.2, 0.95)
            reason += f" +keyword({kw})"
            break
    
    # Roll the dice
    roll = random.random()
    if roll < chance:
        return True, f"{reason} (chance={chance:.0%}, roll={roll:.2f})"
    else:
        return False, f"{reason} (chance={chance:.0%}, roll={roll:.2f} - skipped)"

async def call_agent(
    user_id: int, 
    chat_id: int, 
    message: str, 
    username: str = "user",
    chat_type: str = "private"
) -> str | None:
    """Call gateway API to get agent response"""
    try:
        # Build system prompt with context
        system_prompt = SYSTEM_PROMPT_TEMPLATE
        if system_prompt:
            system_prompt = system_prompt.replace('{chat_id}', str(chat_id))
            system_prompt = system_prompt.replace('{username}', username)
            system_prompt = system_prompt.replace('{chat_type}', chat_type)
        
        async with aiohttp.ClientSession() as session:
            payload = {
                "user_id": user_id,
                "chat_id": chat_id,
                "message": message,
                "username": username,
                "source": "userbot",
                "chat_type": chat_type,
            }
            
            # Add system prompt if available
            if system_prompt:
                payload["system_prompt"] = system_prompt
            
            async with session.post(
                f"{CORE_URL}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response")
                else:
                    print(f"[agent] Error: {resp.status}")
                    return None
    except Exception as e:
        print(f"[agent] Request failed: {e}")
        return None

# ============ USERBOT ACTIONS ============
# These can be called by agent through special commands in response

async def join_chat(client, invite_link: str) -> str:
    """Join a group/channel by invite link or username"""
    try:
        from telethon.tl.functions.messages import ImportChatInviteRequest
        from telethon.tl.functions.channels import JoinChannelRequest
        
        if 'joinchat' in invite_link or '+' in invite_link:
            # Private invite link
            hash_part = invite_link.split('/')[-1].replace('+', '')
            await client(ImportChatInviteRequest(hash_part))
        else:
            # Public username
            username = invite_link.replace('https://t.me/', '').replace('@', '')
            await client(JoinChannelRequest(username))
        return f"✅ Joined {invite_link}"
    except Exception as e:
        return f"❌ Failed to join: {e}"

async def send_message_to(client, target: str, message: str) -> str:
    """Send message to any user/chat"""
    try:
        entity = await client.get_entity(target)
        await client.send_message(entity, message)
        return f"✅ Sent to {target}"
    except Exception as e:
        return f"❌ Failed to send: {e}"

async def get_chat_history(client, chat_id: int, limit: int = 20) -> str:
    """Get recent messages from a chat with message IDs"""
    try:
        messages = []
        async for msg in client.iter_messages(chat_id, limit=limit):
            sender = await msg.get_sender()
            name = getattr(sender, 'username', None) or getattr(sender, 'first_name', 'Unknown')
            text = msg.text or '[media]'
            # Include message ID for delete/edit
            messages.append(f"[{msg.id}] {name}: {text[:100]}")
        return "\n".join(reversed(messages))
    except Exception as e:
        return f"❌ Failed to get history: {e}"

async def delete_message(client, chat_id: int, message_id: int) -> str:
    """Delete a message by ID"""
    try:
        await client.delete_messages(chat_id, [message_id])
        return f"✅ Deleted message {message_id} from {chat_id}"
    except Exception as e:
        return f"❌ Failed to delete: {e}"

async def edit_message(client, chat_id: int, message_id: int, new_text: str) -> str:
    """Edit a message by ID"""
    try:
        await client.edit_message(chat_id, message_id, new_text)
        return f"✅ Edited message {message_id}"
    except Exception as e:
        return f"❌ Failed to edit: {e}"

async def list_dialogs(client, limit: int = 20) -> str:
    """List recent chats"""
    try:
        dialogs = []
        async for dialog in client.iter_dialogs(limit=limit):
            chat_type = "👤" if dialog.is_user else "👥" if dialog.is_group else "📢"
            name = dialog.name or "Unknown"
            dialogs.append(f"{chat_type} {name} (id: {dialog.id})")
        return "\n".join(dialogs)
    except Exception as e:
        return f"❌ Failed to list: {e}"

async def read_channel(client, channel: str, limit: int = 5) -> str:
    """Read recent posts from a channel"""
    try:
        # Handle different formats: @channel, t.me/channel, channel
        original_channel = channel
        if channel.startswith('https://t.me/'):
            channel = channel.replace('https://t.me/', '')
        if channel.startswith('t.me/'):
            channel = channel.replace('t.me/', '')
        if channel.startswith('@'):
            channel_name = channel[1:]  # Remove @ for URL
        else:
            channel_name = channel
            channel = f'@{channel}'
        
        entity = await client.get_entity(channel)
        posts = []
        
        async for msg in client.iter_messages(entity, limit=limit * 2):  # Get more to skip media-only
            date = msg.date.strftime('%Y-%m-%d %H:%M') if msg.date else ''
            post_id = msg.id
            post_link = f"https://t.me/{channel_name}/{post_id}"
            
            # Get text content
            text = msg.text or msg.message or ''
            
            # Check for media and add info
            media_info = ""
            if msg.photo:
                media_info = "📷 [Photo attached]"
            elif msg.video:
                media_info = "🎬 [Video attached]"
            elif msg.document:
                doc_name = ""
                if msg.document.attributes:
                    for attr in msg.document.attributes:
                        if hasattr(attr, 'file_name'):
                            doc_name = f": {attr.file_name}"
                            break
                media_info = f"📎 [File{doc_name}]"
            elif msg.sticker:
                media_info = "🎭 [Sticker]"
            
            # Build post content
            if text:
                # Truncate long posts
                if len(text) > 500:
                    text = text[:500] + '...'
                content = text
                if media_info:
                    content += f"\n{media_info}"
            else:
                if media_info:
                    content = media_info
                else:
                    content = "[Empty post]"
                # Skip media-only posts if we have enough text posts
                if len(posts) >= limit and not text:
                    continue
            
            posts.append(f"📅 {date}\n{content}\n🔗 {post_link}")
            
            if len(posts) >= limit:
                break
        
        if not posts:
            return f"No posts found in {channel}"
        
        header = f"📢 Latest {len(posts)} posts from {channel}:\n\n"
        return header + "\n---\n".join(reversed(posts))
    except Exception as e:
        return f"❌ Failed to read channel: {e}"

async def process_command(client, response: str) -> str | None:
    """Process special commands in agent response"""
    if not response:
        return response
    
    # Parse commands like: [CMD:join:https://t.me/group]
    import re
    
    cmd_pattern = r'\[CMD:(\w+):([^\]]+)\]'
    matches = re.findall(cmd_pattern, response)
    
    for cmd, arg in matches:
        result = ""
        if cmd == "join":
            result = await join_chat(client, arg)
        elif cmd == "send":
            # Format: target|message
            parts = arg.split('|', 1)
            if len(parts) == 2:
                result = await send_message_to(client, parts[0], parts[1])
        elif cmd == "history":
            # Format: chat_id or chat_id:limit
            parts = arg.split(':')
            chat_id = int(parts[0])
            limit = int(parts[1]) if len(parts) > 1 else 20
            result = await get_chat_history(client, chat_id, limit)
        elif cmd == "dialogs":
            result = await list_dialogs(client, int(arg) if arg.isdigit() else 20)
        elif cmd == "channel":
            # Format: @channel or @channel:limit
            parts = arg.split(':')
            channel = parts[0]
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
            result = await read_channel(client, channel, limit)
            print(f"[channel] Read {channel}: {len(result)} chars")
        
        # Replace command with result
        response = response.replace(f"[CMD:{cmd}:{arg}]", result)
    
    return response

# ============ API MODELS ============

class ChannelRequest(BaseModel):
    channel: str
    limit: int = 5

class JoinRequest(BaseModel):
    invite_link: str

class SendRequest(BaseModel):
    target: str
    message: str

class HistoryRequest(BaseModel):
    chat_id: int
    limit: int = 20

class DialogsRequest(BaseModel):
    limit: int = 20

class SendFileRequest(BaseModel):
    target: str  # @username, chat_id, or phone
    file_data: str  # Base64 encoded file content
    filename: str  # Original filename
    caption: str = ""  # Optional caption

class DeleteRequest(BaseModel):
    chat_id: int  # Chat to delete from
    message_id: int  # Message ID to delete

class EditRequest(BaseModel):
    chat_id: int  # Chat containing message
    message_id: int  # Message ID to edit
    new_text: str  # New text content

# ============ API ENDPOINTS ============

@app.get("/health")
async def health():
    """Health check"""
    if telegram_client and telegram_client.is_connected():
        return {"status": "ok", "connected": True}
    return {"status": "starting", "connected": False}

@app.get("/resolve/{username}")
async def api_resolve_username(username: str):
    """Resolve username to user ID"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    try:
        # Handle with or without @
        if not username.startswith('@'):
            username = f'@{username}'
        entity = await telegram_client.get_entity(username)
        return {
            "success": True,
            "id": entity.id,
            "username": getattr(entity, 'username', None),
            "first_name": getattr(entity, 'first_name', None),
            "last_name": getattr(entity, 'last_name', None),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/channel")
async def api_read_channel(req: ChannelRequest):
    """Read posts from a Telegram channel"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await read_channel(telegram_client, req.channel, req.limit)
    return {"success": True, "content": result}

@app.post("/join")
async def api_join_chat(req: JoinRequest):
    """Join a group or channel"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await join_chat(telegram_client, req.invite_link)
    success = not result.startswith("❌")
    return {"success": success, "message": result}

@app.post("/send")
async def api_send_message(req: SendRequest):
    """Send message to any user or chat"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await send_message_to(telegram_client, req.target, req.message)
    success = not result.startswith("❌")
    return {"success": success, "message": result}

@app.post("/history")
async def api_get_history(req: HistoryRequest):
    """Get chat history"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await get_chat_history(telegram_client, req.chat_id, req.limit)
    return {"success": True, "content": result}

@app.post("/dialogs")
async def api_list_dialogs(req: DialogsRequest):
    """List recent dialogs/chats"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await list_dialogs(telegram_client, req.limit)
    return {"success": True, "content": result}

@app.post("/delete")
async def api_delete_message(req: DeleteRequest):
    """Delete a message"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await delete_message(telegram_client, req.chat_id, req.message_id)
    success = not result.startswith("❌")
    return {"success": success, "message": result}

@app.post("/edit")
async def api_edit_message(req: EditRequest):
    """Edit a message"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    result = await edit_message(telegram_client, req.chat_id, req.message_id, req.new_text)
    success = not result.startswith("❌")
    return {"success": success, "message": result}

@app.post("/send_file")
async def api_send_file(req: SendFileRequest):
    """Send file to any user or chat"""
    if not telegram_client:
        raise HTTPException(503, "Telegram client not ready")
    
    import base64
    import tempfile
    
    try:
        # Decode base64 file
        file_bytes = base64.b64decode(req.file_data)
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{req.filename}") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            # Get entity
            entity = await telegram_client.get_entity(req.target)
            
            # Send file
            await telegram_client.send_file(
                entity,
                tmp_path,
                caption=req.caption or None,
                force_document=True  # Send as document, not media
            )
            
            return {"success": True, "message": f"✅ File {req.filename} sent to {req.target}"}
        finally:
            # Cleanup temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to send file: {e}"}

# ============ MAIN ============

async def main():
    global my_user_id, my_username, telegram_client
    global telegram_client  # Needed for API endpoints
    
    if not API_ID or not API_HASH:
        print("ERROR: Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
        return
    
    # Create client
    client = TelegramClient('session/userbot', API_ID, API_HASH)
    
    # Check if session exists
    session_file = 'session/userbot.session'
    if not os.path.exists(session_file):
        print(f"[userbot] ERROR: No session file found at {session_file}")
        print("[userbot] Run auth.py locally first to create session:")
        print("[userbot]   cd userbot && pip install telethon && python auth.py")
        return
    
    # Connect using existing session (no interactive login needed)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("[userbot] ERROR: Session expired or invalid")
        print("[userbot] Run auth.py locally to re-authorize")
        return
    
    me = await client.get_me()
    my_user_id = me.id
    my_username = me.username
    
    # Set global client for API endpoints
    telegram_client = client
    
    print(f"[userbot] Started as @{my_username} ({my_user_id})")
    print(f"[userbot] Chances: DM={RESPONSE_CHANCE_DM:.0%}, Group={RESPONSE_CHANCE_GROUP:.0%}, Mention={RESPONSE_CHANCE_MENTION:.0%}, Reply={RESPONSE_CHANCE_REPLY:.0%}")
    print(f"[userbot] Core: {CORE_URL}")
    print(f"[userbot] API server on http://0.0.0.0:8080")
    if OWNER_ONLY:
        print(f"[userbot] OWNER_ONLY mode: responding only to {OWNER_IDS}")
    else:
        print(f"[userbot] Public mode: responding to everyone")
    
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        global last_response_time
        
        # Get message info
        message = event.message
        text = message.text or message.message or ""
        
        # Log ALL incoming messages
        chat = await event.get_chat()
        chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(event.chat_id)
        print(f"[msg] {chat_name}: {text[:50]}...")
        
        if not text:
            return
        
        # Get sender info
        sender = await event.get_sender()
        if not sender:
            print(f"[msg] No sender info")
            return
        
        # ============ OWNER COMMANDS ============
        # Direct commands from owner (bypass agent)
        if OWNER_IDS and sender.id in OWNER_IDS and text.startswith('/'):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if cmd == '/join':
                result = await join_chat(client, arg)
                await event.reply(result)
                return
            elif cmd == '/send':
                # /send @username message
                p = arg.split(maxsplit=1)
                if len(p) == 2:
                    result = await send_message_to(client, p[0], p[1])
                    await event.reply(result)
                return
            elif cmd == '/history':
                chat_id = int(arg) if arg else event.chat_id
                result = await get_chat_history(client, chat_id)
                await event.reply(result)
                return
            elif cmd == '/dialogs':
                result = await list_dialogs(client, int(arg) if arg.isdigit() else 20)
                await event.reply(result)
                return
            elif cmd == '/stats':
                stats = f"📊 Userbot Stats\n\nActive cooldowns: {len(last_response_time)}\nOwners: {OWNER_IDS}\nWhitelisted: {len(WHITELIST)}"
                await event.reply(stats)
                return
            elif cmd == '/allow':
                # /allow @username - add user to whitelist
                if not arg:
                    await event.reply("Usage: /allow @username")
                    return
                try:
                    if not arg.startswith('@'):
                        arg = f'@{arg}'
                    entity = await client.get_entity(arg)
                    WHITELIST[entity.id] = arg.lstrip('@')
                    save_whitelist(WHITELIST)
                    await event.reply(f"✅ {arg} ({entity.id}) added to whitelist")
                except Exception as e:
                    await event.reply(f"❌ Failed: {e}")
                return
            elif cmd == '/deny':
                # /deny @username - remove user from whitelist
                if not arg:
                    await event.reply("Usage: /deny @username or /deny <user_id>")
                    return
                try:
                    # Try as user_id first
                    if arg.isdigit():
                        uid = int(arg)
                    else:
                        if not arg.startswith('@'):
                            arg = f'@{arg}'
                        entity = await client.get_entity(arg)
                        uid = entity.id
                    
                    if uid in WHITELIST:
                        username = WHITELIST.pop(uid)
                        save_whitelist(WHITELIST)
                        await event.reply(f"✅ @{username} ({uid}) removed from whitelist")
                    else:
                        await event.reply(f"⚠️ User {uid} not in whitelist")
                except Exception as e:
                    await event.reply(f"❌ Failed: {e}")
                return
            elif cmd == '/whitelist':
                # Show current whitelist
                if not WHITELIST:
                    await event.reply("📋 Whitelist is empty")
                else:
                    lines = [f"📋 Whitelist ({len(WHITELIST)}):"]
                    for uid, uname in WHITELIST.items():
                        lines.append(f"  • @{uname} ({uid})")
                    await event.reply("\n".join(lines))
                return
            elif cmd == '/help':
                help_text = """🤖 Userbot Commands:

/join <link> - Join group/channel
/send <user> <msg> - Send message to user
/history [chat_id] - Get chat history
/dialogs [limit] - List recent chats
/stats - Show stats

👑 Admin commands:
/allow @username - Add user to whitelist
/deny @username - Remove from whitelist
/whitelist - Show whitelist

/help - This message"""
                await event.reply(help_text)
                return
            
        # Ignore bots (except whitelisted)
        if IGNORE_BOTS and isinstance(sender, User) and sender.bot:
            if sender.id not in WHITELIST:
                print(f"[skip] Bot {sender.id}: {text[:30]}... (bot not in whitelist)")
                return
        
        sender_name = getattr(sender, 'username', None) or getattr(sender, 'first_name', 'anon')
        chat_id = event.chat_id
        
        # Determine chat type
        chat_type = "private" if event.is_private else "group"
        
        # Decide if we should respond
        should, reason = should_respond(event, text)
        
        if not should:
            # Log skipped messages occasionally
            if random.random() < 0.1:  # 10% of skipped
                print(f"[skip] {sender_name}: {text[:50]}... ({reason})")
            return
        
        # Anti-loop: limit bot-to-bot conversation
        if sender.id == TELEGRAM_BOT_ID and not event.is_private:
            import time
            key = (chat_id, sender.id)
            now = time.time()
            
            # Reset counter if cooldown passed
            last_reset = bot_conversation_reset.get(key, 0)
            if now - last_reset > BOT_COOLDOWN:
                bot_conversation_count[key] = 0
                bot_conversation_reset[key] = now
            
            count = bot_conversation_count.get(key, 0)
            if count >= MAX_BOT_REPLIES:
                print(f"[anti-loop] Ignoring bot in {chat_id} (count={count})")
                return
            
            bot_conversation_count[key] = count + 1
        
        print(f"[respond] {sender_name} in {chat_id}: {text[:100]}...")
        print(f"[respond] Reason: {reason}")
        
        # Show typing
        async with client.action(chat_id, 'typing'):
            # Small delay to feel human
            await asyncio.sleep(random.uniform(1, 3))
            
            # Call agent
            response = await call_agent(
                user_id=sender.id,
                chat_id=chat_id,
                message=text,
                username=sender_name,
                chat_type=chat_type
            )
        
        if response:
            # Process any special commands in response
            response = await process_command(client, response)
            
            # Update cooldown
            last_response_time[chat_id] = datetime.now()
            
            # Send response - clean model artifacts
            if response:
                # Remove thinking blocks with content
                response = re.sub(r'<thinking>[\s\S]*?</thinking>', '', response, flags=re.IGNORECASE)
                # Remove standalone tags
                response = re.sub(r'</?(final|response|answer|output|reply|thinking)>', '', response, flags=re.IGNORECASE).strip()
            # Don't send if response is just command results
            if response and not response.startswith('✅') and not response.startswith('❌'):
                # Random reply (50% in DM, always in groups)
                use_reply = not event.is_private or random.random() < 0.5
                
                if use_reply:
                    await event.reply(response)
                else:
                    await client.send_message(chat_id, response)
                
                print(f"[sent] {'(reply) ' if use_reply else ''}{response[:100]}...")
        else:
            print(f"[error] No response from agent")
    
    print("[userbot] Listening for messages...")
    
    # Run uvicorn and telethon client in parallel
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        client.run_until_disconnected(),
        server.serve()
    )

if __name__ == '__main__':
    asyncio.run(main())
