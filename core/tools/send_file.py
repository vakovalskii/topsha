"""Send file to chat"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from config import CONFIG
from logger import tool_logger
from models import ToolResult, ToolContext


async def tool_send_file(args: dict, ctx: ToolContext) -> ToolResult:
    """Send file from workspace to chat"""
    import asyncio
    
    path = args.get("path", "")
    caption = args.get("caption", "")
    
    if not path:
        return ToolResult(False, error="Path required")
    
    # Normalize path
    if not path.startswith("/"):
        path = os.path.join(ctx.cwd, path)
    
    # Check file exists (with retry for race condition)
    for attempt in range(3):
        if os.path.exists(path):
            break
        tool_logger.info(f"File not ready yet, waiting... ({attempt+1}/3)")
        await asyncio.sleep(1)
    
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
