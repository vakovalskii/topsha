"""Send file to chat"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import aiohttp
from config import CONFIG
from logger import tool_logger
from models import ToolResult, ToolContext
from tools.files import normalize_path


async def tool_send_file(args: dict, ctx: ToolContext) -> ToolResult:
    """Send file from workspace to chat"""
    path = args.get("path", "")
    caption = args.get("caption", "")
    
    if not path:
        return ToolResult(False, error="Path required")
    
    # Normalize path
    path = normalize_path(path, ctx.cwd)
    
    # Check file exists (with retry for race condition / sync delay)
    for attempt in range(5):
        if os.path.exists(path):
            # Also check file size > 0 (not still being written)
            try:
                if os.path.getsize(path) > 0:
                    break
            except:
                pass
        tool_logger.info(f"File not ready yet, waiting... ({attempt+1}/5)")
        await asyncio.sleep(2)
    
    if not os.path.exists(path):
        return ToolResult(False, error=f"File not found: {path}")
    
    # Check file size
    file_size = os.path.getsize(path)
    if file_size > 50 * 1024 * 1024:
        return ToolResult(False, error="File too large (max 50MB)")
    
    tool_logger.info(f"Sending file: {path}")
    
    # Determine callback URL based on source
    callback_url = CONFIG.userbot_url if ctx.source == "userbot" else CONFIG.bot_url
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{callback_url}/send_file",
                json={
                    "chat_id": ctx.chat_id,
                    "file_path": path,
                    "caption": caption
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                data = await resp.json()
                if data.get("success"):
                    tool_logger.info(f"File sent: {path}")
                    return ToolResult(True, output=f"✅ File sent: {os.path.basename(path)}")
                else:
                    return ToolResult(False, error=data.get("error", "Failed to send"))
    except Exception as e:
        tool_logger.error(f"Send file error: {e}")
        return ToolResult(False, error=str(e))
