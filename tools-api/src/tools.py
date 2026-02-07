"""Built-in tool definitions"""

# SHARED tools - available to all agents, managed via admin panel
SHARED_TOOLS = {
    "run_command": {
        "enabled": True,
        "name": "run_command",
        "description": "Run a shell command. Use for: git, npm, pip, python, system ops.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }
    },
    "read_file": {
        "enabled": True,
        "name": "read_file",
        "description": "Read file contents. Always read before editing.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "offset": {"type": "integer", "description": "Starting line (1-based)"},
                "limit": {"type": "integer", "description": "Number of lines"}
            },
            "required": ["path"]
        }
    },
    "write_file": {
        "enabled": True,
        "name": "write_file",
        "description": "Write content to file. Creates if doesn't exist.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    },
    "edit_file": {
        "enabled": True,
        "name": "edit_file",
        "description": "Edit file by replacing text. old_text must match exactly.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "old_text": {"type": "string", "description": "Text to find"},
                "new_text": {"type": "string", "description": "Replacement text"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    "delete_file": {
        "enabled": True,
        "name": "delete_file",
        "description": "Delete a file within workspace.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"}
            },
            "required": ["path"]
        }
    },
    "search_files": {
        "enabled": True,
        "name": "search_files",
        "description": "Search for files by glob pattern.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"}
            },
            "required": ["pattern"]
        }
    },
    "search_text": {
        "enabled": True,
        "name": "search_text",
        "description": "Search text in files using grep.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text/regex to search"},
                "path": {"type": "string", "description": "Directory to search"},
                "ignore_case": {"type": "boolean", "description": "Case insensitive"}
            },
            "required": ["pattern"]
        }
    },
    "list_directory": {
        "enabled": True,
        "name": "list_directory",
        "description": "List directory contents.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"}
            },
            "required": []
        }
    },
    "search_web": {
        "enabled": True,
        "name": "search_web",
        "description": "Search the internet for current info, news, docs.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    "fetch_page": {
        "enabled": True,
        "name": "fetch_page",
        "description": "Fetch and parse URL content as markdown.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"}
            },
            "required": ["url"]
        }
    },
    "memory": {
        "enabled": True,
        "name": "memory",
        "description": "Long-term memory. Save/read important info across sessions.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "append", "clear"]},
                "content": {"type": "string", "description": "Text to save (for append)"}
            },
            "required": ["action"]
        }
    },
    "schedule_task": {
        "enabled": True,
        "name": "schedule_task",
        "description": "Schedule recurring or delayed tasks. IMPORTANT: 'content' is a TEXT PROMPT (not code!) that will be sent to the agent. Example: content='Найди курс доллара и отправь в ЛС'. The agent will execute this prompt with all its tools.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "cancel", "run"], "description": "add=create, list=show, cancel=remove, run=execute now"},
                "type": {"type": "string", "enum": ["message", "agent"], "description": "'message'=send text reminder, 'agent'=run agent with prompt (can use tools)"},
                "content": {"type": "string", "description": "TEXT PROMPT for agent (NOT code!). Example: 'Найди новости про X и отправь мне'"},
                "delay_minutes": {"type": "integer", "description": "Minutes before first run (default: 1)"},
                "recurring": {"type": "boolean", "description": "Repeat after execution?"},
                "interval_minutes": {"type": "integer", "description": "Repeat interval in minutes (min: 1)"},
                "task_id": {"type": "string", "description": "Task ID (for cancel/run)"}
            },
            "required": ["action"]
        }
    },
    "manage_tasks": {
        "enabled": True,
        "name": "manage_tasks",
        "description": "Todo list for planning complex tasks.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "update", "list", "clear"]},
                "id": {"type": "string", "description": "Task ID"},
                "content": {"type": "string", "description": "Task description"},
                "status": {"type": "string", "enum": ["pending", "done", "cancelled"]}
            },
            "required": ["action"]
        }
    },
    "search_tools": {
        "enabled": True,
        "name": "search_tools",
        "description": "🔍 DISCOVER MORE TOOLS! Search available tools by keyword. Use when you need capabilities not in your base toolkit (e.g. 'docker', 'telegram', 'presentation', 'web').",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (e.g. 'docker', 'telegram', 'file')"},
                "source": {"type": "string", "enum": ["all", "builtin", "mcp"], "description": "Filter by source"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"}
            },
            "required": ["query"]
        }
    },
    "load_tools": {
        "enabled": True,
        "name": "load_tools",
        "description": "Load additional tools into your session after finding them with search_tools. Tools will be available immediately.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}, "description": "List of tool names to load"}
            },
            "required": ["names"]
        }
    },
    "install_skill": {
        "enabled": True,
        "name": "install_skill",
        "description": "Install a skill from Anthropic's skills repository. Skills add capabilities like creating presentations, documents, etc.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (e.g. 'pptx', 'docx', 'xlsx')"},
                "source": {"type": "string", "enum": ["anthropic", "url"], "description": "Source: 'anthropic' for official skills, 'url' for custom"}
            },
            "required": ["name"]
        }
    },
    "list_skills": {
        "enabled": True,
        "name": "list_skills",
        "description": "List available and installed skills.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "installed_only": {"type": "boolean", "description": "Show only installed skills"}
            },
            "required": []
        }
    },
    # ============ TELEGRAM USERBOT TOOLS ============
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

# Bot-only tools (not managed by this API, always available for bot)
BOT_ONLY_TOOLS = ["send_file", "send_dm", "manage_message", "ask_user"]

# Userbot-only tools (require userbot to be running)
USERBOT_TOOLS = [
    "telegram_channel", "telegram_join", "telegram_send", 
    "telegram_history", "telegram_dialogs", "telegram_delete", 
    "telegram_edit", "telegram_resolve"
]
