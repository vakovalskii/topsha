"""
First-time authorization script
Run this LOCALLY (not in Docker) to create session file
Then the session can be used in Docker without interactive login

IMPORTANT: Run from the userbot directory:
  cd userbot && python auth.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Ensure we're in the userbot directory
SCRIPT_DIR = Path(__file__).parent.absolute()
os.chdir(SCRIPT_DIR)

from telethon import TelegramClient
from telethon.sessions import StringSession


def get_secret(name, prompt):
    """Read from secrets or ask interactively"""
    # Try multiple paths (running from userbot/ or project root)
    paths = [
        SCRIPT_DIR / '..' / 'secrets' / f'{name}.txt',  # ../secrets/
        SCRIPT_DIR / 'secrets' / f'{name}.txt',          # ./secrets/
        Path(f'../secrets/{name}.txt'),                   # relative ../secrets/
    ]
    
    for path in paths:
        if path.exists():
            value = path.read_text().strip()
            if value:
                return value
    
    return input(f"{prompt}: ")


async def main():
    """Main authorization flow with proper async context"""
    from telethon.errors import FloodWaitError
    
    print("=" * 50)
    print("Telegram Userbot Authorization")
    print("=" * 50)
    print()
    
    api_id = get_secret('telegram_api_id', 'API ID')
    api_hash = get_secret('telegram_api_hash', 'API Hash')
    phone = get_secret('telegram_phone', 'Phone (with country code, e.g. +79001234567)')
    
    print()
    print(f"API ID: {api_id}")
    print(f"Phone: {phone}")
    print()
    
    # Create session directory in the correct location (userbot/session/)
    session_dir = SCRIPT_DIR / 'session'
    session_dir.mkdir(exist_ok=True)
    session_path = session_dir / 'userbot'
    
    print(f"Session will be saved to: {session_path}.session")
    print()
    
    # Create client INSIDE async context (fixes Python 3.14 issue)
    client = TelegramClient(str(session_path), int(api_id), api_hash)
    
    try:
        await client.start(phone=phone)
    except FloodWaitError as e:
        print(f"\n⚠️ FloodWait: Need to wait {e.seconds} seconds")
        print(f"   Telegram blocked requests due to too many attempts")
        print(f"\n   Please wait and try again in {e.seconds // 60} min {e.seconds % 60} sec")
        return
    
    me = await client.get_me()
    print()
    print("=" * 50)
    print(f"✅ Authorized as @{me.username} ({me.id})")
    print("=" * 50)
    print()
    print(f"Session saved to: {session_path}.session")
    print()
    print("Now you can run userbot in Docker:")
    print("  docker compose --profile userbot up -d")
    print()
    
    await client.disconnect()


if __name__ == "__main__":
    # Python 3.10+ compatible way to run async main
    # Works on Python 3.14 where asyncio.run() requires explicit loop policy
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "no current event loop" in str(e).lower():
            # Fallback for Python 3.14+ on some systems
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(main())
            finally:
                loop.close()
        else:
            raise
