"""Global bot state"""

import asyncio
import json
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_TOKEN

logger = logging.getLogger("bot.state")

# Bot instance
bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Dispatcher
dp = Dispatcher()

# Bot info (set on startup)
bot_username = ""
bot_id = 0

# AFK state
afk_until = 0.0
afk_reason = ""

# Anti-loop tracking
bot_conversation_count: dict[tuple[int, int], int] = {}
bot_conversation_reset: dict[tuple[int, int], float] = {}

# ============ USERNAME REGISTRY ============
# Maps @username (lowercase, without @) -> user_id
# Persisted to disk so it survives restarts

_USERNAME_REGISTRY_PATH = os.getenv("USERNAME_REGISTRY_PATH", "/data/username_registry.json")
_username_registry: dict[str, int] = {}


def _load_username_registry():
    """Load username registry from disk"""
    global _username_registry
    try:
        if os.path.exists(_USERNAME_REGISTRY_PATH):
            with open(_USERNAME_REGISTRY_PATH, "r") as f:
                _username_registry = json.load(f)
            logger.info(f"[registry] Loaded {len(_username_registry)} username mappings")
    except Exception as e:
        logger.error(f"[registry] Failed to load: {e}")
        _username_registry = {}


def _save_username_registry():
    """Save username registry to disk"""
    try:
        os.makedirs(os.path.dirname(_USERNAME_REGISTRY_PATH), exist_ok=True)
        with open(_USERNAME_REGISTRY_PATH, "w") as f:
            json.dump(_username_registry, f, indent=2)
    except Exception as e:
        logger.error(f"[registry] Failed to save: {e}")


def register_username(username: str | None, user_id: int):
    """Register a username -> user_id mapping"""
    if not username or not user_id:
        return
    key = username.lower().lstrip("@")
    if _username_registry.get(key) != user_id:
        _username_registry[key] = user_id
        _save_username_registry()
        logger.info(f"[registry] Registered @{key} -> {user_id}")


def resolve_username(username: str) -> int | None:
    """Resolve @username to user_id. Returns None if not found."""
    key = username.lower().lstrip("@")
    return _username_registry.get(key)


def get_all_usernames() -> dict[str, int]:
    """Get all known username -> user_id mappings"""
    return dict(_username_registry)


# Load on import
_load_username_registry()


def is_afk() -> bool:
    """Check if bot is in AFK mode"""
    return afk_until > 0 and asyncio.get_event_loop().time() < afk_until


def set_afk(minutes: int, reason: str):
    """Set AFK mode"""
    global afk_until, afk_reason
    if minutes <= 0:
        afk_until = 0
        afk_reason = ""
    else:
        afk_until = asyncio.get_event_loop().time() + minutes * 60
        afk_reason = reason


def clear_afk():
    """Clear AFK mode"""
    global afk_until, afk_reason
    afk_until = 0
    afk_reason = ""
