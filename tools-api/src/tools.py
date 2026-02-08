"""
Built-in tool definitions - Legacy compatibility layer

This module re-exports tools from the modular structure in src/tools/
for backward compatibility with existing code.

New structure:
- src/tools/files.py      → File operations
- src/tools/web.py        → Web & search
- src/tools/system.py     → Commands, memory, tasks
- src/tools/telegram.py   → Telegram userbot
- src/tools/discovery.py  → Tool discovery & skills
"""

from .tool_defs import get_all_tools, BOT_ONLY_TOOLS, USERBOT_TOOLS

# Re-export for backward compatibility
SHARED_TOOLS = get_all_tools()

__all__ = ["SHARED_TOOLS", "BOT_ONLY_TOOLS", "USERBOT_TOOLS"]
