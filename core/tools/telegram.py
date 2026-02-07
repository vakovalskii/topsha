"""Telegram userbot tools - call userbot HTTP API"""

import os
import aiohttp
from models import ToolResult, ToolContext

USERBOT_URL = os.getenv("USERBOT_URL", "http://userbot:8080")


async def _call_userbot(endpoint: str, method: str = "POST", json_data: dict = None) -> dict:
    """Call userbot HTTP API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{USERBOT_URL}/{endpoint}"
            
            if method == "GET":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    return await resp.json()
            else:
                async with session.post(url, json=json_data or {}, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    return await resp.json()
                    
    except aiohttp.ClientError as e:
        return {"success": False, "error": f"Userbot connection failed: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def tool_telegram_channel(args: dict, ctx: ToolContext) -> ToolResult:
    """Read posts from a Telegram channel"""
    channel = args.get("channel", "")
    limit = args.get("limit", 5)
    
    if not channel:
        return ToolResult(False, error="Channel required (e.g. @channel or t.me/channel)")
    
    result = await _call_userbot("channel", json_data={"channel": channel, "limit": limit})
    
    if result.get("success"):
        return ToolResult(True, output=result.get("content", "No posts found"))
    else:
        return ToolResult(False, error=result.get("error", "Failed to read channel"))


async def tool_telegram_join(args: dict, ctx: ToolContext) -> ToolResult:
    """Join a Telegram group or channel"""
    invite_link = args.get("invite_link", "")
    
    if not invite_link:
        return ToolResult(False, error="Invite link or username required")
    
    result = await _call_userbot("join", json_data={"invite_link": invite_link})
    
    if result.get("success"):
        return ToolResult(True, output=result.get("message", "Joined successfully"))
    else:
        return ToolResult(False, error=result.get("message", result.get("error", "Failed to join")))


async def tool_telegram_send(args: dict, ctx: ToolContext) -> ToolResult:
    """Send message to a Telegram user or chat"""
    target = args.get("target", "")
    message = args.get("message", "")
    
    if not target:
        return ToolResult(False, error="Target required (@username, phone, or chat_id)")
    if not message:
        return ToolResult(False, error="Message text required")
    
    result = await _call_userbot("send", json_data={"target": target, "message": message})
    
    if result.get("success"):
        return ToolResult(True, output=result.get("message", "Message sent"))
    else:
        return ToolResult(False, error=result.get("message", result.get("error", "Failed to send")))


async def tool_telegram_history(args: dict, ctx: ToolContext) -> ToolResult:
    """Get chat history"""
    chat_id = args.get("chat_id")
    limit = args.get("limit", 20)
    
    if not chat_id:
        return ToolResult(False, error="chat_id required")
    
    result = await _call_userbot("history", json_data={"chat_id": int(chat_id), "limit": limit})
    
    if result.get("success"):
        return ToolResult(True, output=result.get("content", "No messages"))
    else:
        return ToolResult(False, error=result.get("error", "Failed to get history"))


async def tool_telegram_dialogs(args: dict, ctx: ToolContext) -> ToolResult:
    """List recent dialogs"""
    limit = args.get("limit", 20)
    
    result = await _call_userbot("dialogs", json_data={"limit": limit})
    
    if result.get("success"):
        return ToolResult(True, output=result.get("content", "No dialogs"))
    else:
        return ToolResult(False, error=result.get("error", "Failed to list dialogs"))


async def tool_telegram_delete(args: dict, ctx: ToolContext) -> ToolResult:
    """Delete a message"""
    chat_id = args.get("chat_id")
    message_id = args.get("message_id")
    
    if not chat_id or not message_id:
        return ToolResult(False, error="chat_id and message_id required")
    
    result = await _call_userbot("delete", json_data={
        "chat_id": int(chat_id),
        "message_id": int(message_id)
    })
    
    if result.get("success"):
        return ToolResult(True, output=result.get("message", "Message deleted"))
    else:
        return ToolResult(False, error=result.get("message", result.get("error", "Failed to delete")))


async def tool_telegram_edit(args: dict, ctx: ToolContext) -> ToolResult:
    """Edit a message"""
    chat_id = args.get("chat_id")
    message_id = args.get("message_id")
    new_text = args.get("new_text", "")
    
    if not chat_id or not message_id:
        return ToolResult(False, error="chat_id and message_id required")
    if not new_text:
        return ToolResult(False, error="new_text required")
    
    result = await _call_userbot("edit", json_data={
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "new_text": new_text
    })
    
    if result.get("success"):
        return ToolResult(True, output=result.get("message", "Message edited"))
    else:
        return ToolResult(False, error=result.get("message", result.get("error", "Failed to edit")))


async def tool_telegram_resolve(args: dict, ctx: ToolContext) -> ToolResult:
    """Resolve username to user info"""
    username = args.get("username", "")
    
    if not username:
        return ToolResult(False, error="Username required")
    
    # Remove @ if present for API call
    clean_username = username.lstrip("@")
    
    result = await _call_userbot(f"resolve/{clean_username}", method="GET")
    
    if result.get("success"):
        info = []
        info.append(f"👤 @{result.get('username', clean_username)}")
        if result.get("first_name"):
            info.append(f"Name: {result.get('first_name')} {result.get('last_name', '')}")
        info.append(f"ID: {result.get('id')}")
        return ToolResult(True, output="\n".join(info))
    else:
        return ToolResult(False, error=result.get("error", "Failed to resolve username"))
