"""
Tools API - Modular Tool Definitions

Структура:
- files.py      → read_file, write_file, edit_file, delete_file, search_files, search_text, list_directory
- web.py        → search_web, fetch_page
- system.py     → run_command, memory, manage_tasks, schedule_task
- telegram.py   → telegram_channel, telegram_send, telegram_history, etc.
- discovery.py  → search_tools, load_tools, install_skill, list_skills

Каждый файл экспортирует:
- TOOLS: Dict[str, ToolDefinition] - определения tools
"""

from typing import Dict, Any
import importlib
from pathlib import Path

# Registry
ALL_TOOLS: Dict[str, dict] = {}

# Tool categories for documentation
CATEGORIES = {
    "files": "File Operations",
    "web": "Web & Search",
    "system": "System & Tasks",
    "telegram": "Telegram Userbot",
    "discovery": "Tool Discovery & Skills"
}


def load_all_tools() -> Dict[str, dict]:
    """Load all tool definitions from modules"""
    global ALL_TOOLS
    
    if ALL_TOOLS:
        return ALL_TOOLS
    
    tools_dir = Path(__file__).parent
    
    for file in sorted(tools_dir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        
        module_name = file.stem
        try:
            module = importlib.import_module(f".{module_name}", package="src.tool_defs")
            
            if hasattr(module, "TOOLS"):
                ALL_TOOLS.update(module.TOOLS)
        except Exception as e:
            print(f"[tools-api] Failed to load {module_name}: {e}")
    
    return ALL_TOOLS


def get_all_tools() -> Dict[str, dict]:
    """Get all tool definitions"""
    return load_all_tools()


def get_tools_by_category(category: str) -> Dict[str, dict]:
    """Get tools filtered by category/module"""
    all_tools = load_all_tools()
    
    # Map category to source prefix
    source_map = {
        "telegram": "builtin:userbot",
        "files": "builtin",
        "web": "builtin",
        "system": "builtin",
        "discovery": "builtin"
    }
    
    if category not in source_map:
        return {}
    
    prefix = source_map[category]
    return {
        name: tool for name, tool in all_tools.items()
        if tool.get("source", "builtin").startswith(prefix)
    }


# Bot-only tools (not managed by this API, always available for bot)
BOT_ONLY_TOOLS = ["send_file", "send_dm", "manage_message", "ask_user"]

# Userbot-only tools (require userbot to be running)
USERBOT_TOOLS = [
    "telegram_channel", "telegram_join", "telegram_send", 
    "telegram_history", "telegram_dialogs", "telegram_delete", 
    "telegram_edit", "telegram_resolve"
]
