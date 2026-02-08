"""Telegram Userbot Tools

Tools for interacting with Telegram via userbot.
Requires userbot service to be running.
"""

TOOLS = {
    "telegram_channel": {
        "enabled": True,
        "name": "telegram_channel",
        "description": "Read posts from a Telegram channel. Use for t.me links - fetch_page doesn't work for Telegram!",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel username (@channel) or t.me link"},
                "limit": {"type": "integer", "description": "Number of posts to fetch (default: 5)"}
            },
            "required": ["channel"]
        }
    },
    
    "telegram_join": {
        "enabled": True,
        "name": "telegram_join",
        "description": "Join a Telegram group or channel by invite link or username.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "invite_link": {"type": "string", "description": "Invite link (t.me/+xxx) or username (@channel)"}
            },
            "required": ["invite_link"]
        }
    },
    
    "telegram_send": {
        "enabled": True,
        "name": "telegram_send",
        "description": "Send a message to any Telegram user or chat.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Username (@user), phone, or chat_id"},
                "message": {"type": "string", "description": "Message text to send"}
            },
            "required": ["target", "message"]
        }
    },
    
    "telegram_history": {
        "enabled": True,
        "name": "telegram_history",
        "description": "Get message history from a chat. Returns message IDs for delete/edit.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "integer", "description": "Chat ID to get history from"},
                "limit": {"type": "integer", "description": "Number of messages (default: 20)"}
            },
            "required": ["chat_id"]
        }
    },
    
    "telegram_dialogs": {
        "enabled": True,
        "name": "telegram_dialogs",
        "description": "List recent Telegram chats/dialogs.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Number of dialogs (default: 20)"}
            },
            "required": []
        }
    },
    
    "telegram_delete": {
        "enabled": True,
        "name": "telegram_delete",
        "description": "Delete a message in a chat. Get message_id from telegram_history.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "integer", "description": "Chat ID"},
                "message_id": {"type": "integer", "description": "Message ID to delete"}
            },
            "required": ["chat_id", "message_id"]
        }
    },
    
    "telegram_edit": {
        "enabled": True,
        "name": "telegram_edit",
        "description": "Edit a message in a chat. Get message_id from telegram_history.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "integer", "description": "Chat ID"},
                "message_id": {"type": "integer", "description": "Message ID to edit"},
                "new_text": {"type": "string", "description": "New message text"}
            },
            "required": ["chat_id", "message_id", "new_text"]
        }
    },
    
    "telegram_resolve": {
        "enabled": True,
        "name": "telegram_resolve",
        "description": "Resolve Telegram username to user ID and info.",
        "source": "builtin:userbot",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to resolve (@username)"}
            },
            "required": ["username"]
        }
    }
}
