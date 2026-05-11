"""Core API client"""

from typing import Optional
import aiohttp

from config import CORE_URL


class CoreResponse:
    def __init__(self, response: Optional[str], disabled: bool = False, access_denied: bool = False):
        self.response = response
        self.disabled = disabled
        self.access_denied = access_denied


async def call_core(
    user_id: int,
    chat_id: int,
    message: str,
    username: str,
    chat_type: str
) -> CoreResponse:
    """Call Core API for agent processing"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CORE_URL}/api/chat",
                json={
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "message": message,
                    "username": username,
                    "source": "bot",
                    "chat_type": chat_type
                },
                timeout=aiohttp.ClientTimeout(total=300)  # 5 min: agent may need 20+ iterations with web search
            ) as resp:
                if resp.status != 200:
                    print(f"[core] Error: {resp.status}")
                    return CoreResponse(None)
                data = await resp.json()
                return CoreResponse(
                    response=data.get("response"),
                    disabled=data.get("disabled", False),
                    access_denied=data.get("access_denied", False)
                )
    except Exception as e:
        print(f"[core] Request failed: {e}")
        return CoreResponse(None)


async def clear_session(user_id: int) -> bool:
    """Clear user session in core"""
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{CORE_URL}/api/clear",
                json={"user_id": user_id}
            )
        return True
    except:
        return False


async def upload_file_to_core(user_id: int, filename: str, data: bytes) -> dict | None:
    """Upload file to core for saving to user workspace"""
    try:
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field("user_id", str(user_id))
            form.add_field("filename", filename)
            form.add_field("file", data, filename=filename)
            async with session.post(
                f"{CORE_URL}/api/upload",
                data=form,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[upload] Failed: {e}")
    return None
