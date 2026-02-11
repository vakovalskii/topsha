"""Send direct message to user"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from config import CONFIG
from logger import tool_logger
from models import ToolResult, ToolContext


async def _resolve_username(username: str) -> int | None:
    """Resolve @username to user_id via bot's registry"""
    bot_url = CONFIG.bot_url
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{bot_url}/resolve_username",
                json={"username": username},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    return data.get("user_id")
                else:
                    tool_logger.warning(f"Username resolve failed: {data.get('error')}")
                    return None
    except Exception as e:
        tool_logger.error(f"Username resolve error: {e}")
        return None


async def tool_send_dm(args: dict, ctx: ToolContext) -> ToolResult:
    """Send private message to a user by user_id or @username"""
    target = args.get("user_id") or args.get("target", "")
    text = args.get("text", "")
    
    if not target:
        return ToolResult(False, error="user_id or @username required")
    
    if not text:
        return ToolResult(False, error="text required")
    
    # Resolve target to numeric user_id
    user_id = None
    target_str = str(target).strip()
    
    if target_str.startswith("@"):
        # It's a username - resolve it
        resolved = await _resolve_username(target_str)
        if resolved:
            user_id = resolved
            tool_logger.info(f"Resolved {target_str} -> {user_id}")
        else:
            return ToolResult(False, error=f"Unknown user {target_str}. User must have messaged the bot at least once.")
    else:
        # Try as numeric user_id
        try:
            user_id = int(target_str)
        except (ValueError, TypeError):
            # Maybe username without @
            resolved = await _resolve_username(target_str)
            if resolved:
                user_id = resolved
                tool_logger.info(f"Resolved @{target_str} -> {user_id}")
            else:
                return ToolResult(False, error=f"Invalid user_id '{target_str}'. Provide numeric ID or @username.")
    
    # Security: log DMs to other users for audit
    if user_id != ctx.user_id:
        tool_logger.info(f"Sending DM to another user: {user_id} (from {ctx.user_id})")
    
    callback_url = CONFIG.userbot_url if ctx.source == "userbot" else CONFIG.bot_url
    
    tool_logger.info(f"Sending DM to {user_id}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{callback_url}/send_dm",
                json={
                    "user_id": user_id,
                    "text": text
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    return ToolResult(True, output=f"✅ DM sent to {target_str}")
                return ToolResult(False, error=data.get("error", "Failed to send DM"))
    
    except Exception as e:
        tool_logger.error(f"Send DM error: {e}")
        return ToolResult(False, error=str(e))
