"""Internationalization - all bot-facing user messages"""

import os
import json

LOCALE_FILE = "/data/bot_locale.json"

STRINGS = {
    "ru": {
        # Commands
        "cmd_start": "<b>🤖 Coding Agent</b>\n\n{group_hint}/clear - Сбросить сессию\n/status - Статус",
        "cmd_start_group_hint": "💬 В группах: @{bot_username} или ответ\n\n",
        "cmd_clear_ok": "🗑 Сессия очищена",
        "cmd_clear_fail": "❌ Не удалось очистить сессию",
        "cmd_status": "<b>📊 Статус</b>\nМодель: <code>{model}</code>\nCore: <code>{core_url}</code>",
        "cmd_afk_only_owner": "Только хозяин может меня отправить по делам 😏",
        "cmd_afk_set": "Ладно, {reason}. Буду через {minutes} мин ✌️",
        "cmd_afk_back": "Я вернулся! 🎉",

        # Voice
        "voice_too_long": "🎤 Слишком длинное голосовое ({duration}с, макс {max}с)",
        "voice_busy": "⏳ Сервер занят, попробуй через минуту",
        "voice_transcribe_fail": "🎤 Не удалось распознать: {error}",
        "voice_empty": "🎤 Не удалось распознать речь",
        "voice_prefix": "[Голосовое сообщение, распознанный текст:]",

        # Messages
        "busy": "⏳ Сервер занят, попробуй через минуту",
        "injection": "Хорошая попытка 😏",
        "error": "❌ Ошибка: {error}",
        "no_response": "(нет ответа)",

        # Access
        "access_denied": "🔒 Доступ запрещён",
        "access_auth_required": "🔒 Для использования бота нужна авторизация",

        # Agent (appended to tool results to enforce language)
        "agent_language_reminder": "\n\n[ВАЖНО: Ответь пользователю НА РУССКОМ ЯЗЫКЕ. Переведи данные и дай краткий ответ по-русски.]",
    },
    "en": {
        # Commands
        "cmd_start": "<b>🤖 Coding Agent</b>\n\n{group_hint}/clear - Reset session\n/status - Status",
        "cmd_start_group_hint": "💬 In groups: @{bot_username} or reply\n\n",
        "cmd_clear_ok": "🗑 Session cleared",
        "cmd_clear_fail": "❌ Failed to clear session",
        "cmd_status": "<b>📊 Status</b>\nModel: <code>{model}</code>\nCore: <code>{core_url}</code>",
        "cmd_afk_only_owner": "Only the owner can send me away 😏",
        "cmd_afk_set": "OK, {reason}. Back in {minutes} min ✌️",
        "cmd_afk_back": "I'm back! 🎉",

        # Voice
        "voice_too_long": "🎤 Voice too long ({duration}s, max {max}s)",
        "voice_busy": "⏳ Server busy, try again in a minute",
        "voice_transcribe_fail": "🎤 Failed to transcribe: {error}",
        "voice_empty": "🎤 Could not recognize speech",
        "voice_prefix": "[Voice message, transcribed text:]",

        # Messages
        "busy": "⏳ Server busy, try again in a minute",
        "injection": "Nice try 😏",
        "error": "❌ Error: {error}",
        "no_response": "(no response)",

        # Access
        "access_denied": "🔒 Access denied",
        "access_auth_required": "🔒 Authorization required",

        # Agent
        "agent_language_reminder": "",  # No reminder needed for English
    },
}

_locale_cache = {"lang": None, "mtime": 0}


def get_locale() -> str:
    """Get current locale from config file or env"""
    try:
        if os.path.exists(LOCALE_FILE):
            mtime = os.path.getmtime(LOCALE_FILE)
            if mtime != _locale_cache["mtime"]:
                with open(LOCALE_FILE) as f:
                    data = json.load(f)
                _locale_cache["lang"] = data.get("language", "ru")
                _locale_cache["mtime"] = mtime
            if _locale_cache["lang"]:
                return _locale_cache["lang"]
    except:
        pass
    return os.getenv("BOT_LANGUAGE", "ru")


def t(key: str, **kwargs) -> str:
    """Get translated string by key with optional format args"""
    lang = get_locale()
    strings = STRINGS.get(lang, STRINGS["ru"])
    text = strings.get(key, STRINGS["ru"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
