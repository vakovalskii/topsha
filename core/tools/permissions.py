"""Tool Permissions - Allowlist/Denylist by session type

Like OpenClaw's sandbox.mode:
- Main (DM): All tools allowed
- Group: Restricted tools
- Sandbox: Minimal tools

This provides defense-in-depth: even if prompt injection succeeds,
dangerous tools are not available in group/sandbox contexts.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("core.permissions")

# Default permissions by session type
# These can be overridden via /workspace/_shared/tool_permissions.json

DEFAULT_PERMISSIONS = {
    # Main session (DM with admin/trusted user) - full access minus send_dm
    "main": {
        "mode": "denylist",
        "tools": [
            "send_dm",  # Not needed in DM - bot response IS the message
        ],
        "description": "Full access for direct messages (except send_dm)"
    },
    
    # Group sessions - restricted
    "group": {
        "mode": "denylist",
        "tools": [
            "send_dm",        # Don't spam DMs from groups
            "manage_message", # Don't edit messages in groups
            "schedule_task",  # No scheduled tasks from groups
        ],
        "description": "Restricted access for group chats"
    },
    
    # Sandbox mode (untrusted users) - minimal
    "sandbox": {
        "mode": "allowlist",
        "tools": [
            "run_command",
            "read_file",
            "write_file",
            "edit_file",
            "delete_file",
            "search_files",
            "search_text",
            "list_directory",
            "memory",
            "manage_tasks",
            "search_tools",   # Can discover tools
            "load_tools",     # Can load tools dynamically
            "install_skill",
            "list_skills",
        ],
        "description": "Minimal tools for sandboxed sessions"
    },
    
    # Userbot - no telegram-specific tools
    "userbot": {
        "mode": "denylist",
        "tools": [
            "send_file",
            "send_dm",
            "manage_message",
            "ask_user",
        ],
        "description": "Userbot cannot use telegram-specific tools"
    }
}

# Dangerous tools that require extra caution
DANGEROUS_TOOLS = {
    "run_command": "Can execute arbitrary shell commands",
    "write_file": "Can overwrite files",
    "delete_file": "Can delete files",
    "schedule_task": "Can schedule persistent tasks",
}

# Tools that should never be available in sandbox
SANDBOX_DENIED = {
    "send_dm",
    "manage_message",
    "schedule_task",
    "ask_user",
}


@dataclass
class PermissionResult:
    allowed: bool
    reason: str
    tool: str
    session_type: str


class ToolPermissions:
    """Manage tool access by session type"""
    
    def __init__(self):
        self.permissions = DEFAULT_PERMISSIONS.copy()
        self._load_custom_permissions()
        logger.info(f"Tool permissions loaded: {list(self.permissions.keys())}")
    
    def _load_custom_permissions(self):
        """Load custom permissions from file"""
        perm_file = Path("/workspace/_shared/tool_permissions.json")
        if perm_file.exists():
            try:
                custom = json.loads(perm_file.read_text())
                for session_type, config in custom.items():
                    if session_type in self.permissions:
                        self.permissions[session_type].update(config)
                    else:
                        self.permissions[session_type] = config
                logger.info(f"Loaded custom permissions from {perm_file}")
            except Exception as e:
                logger.error(f"Failed to load custom permissions: {e}")
    
    def check_permission(
        self, 
        tool_name: str, 
        session_type: str = "main",
        source: str = "bot"
    ) -> PermissionResult:
        """Check if tool is allowed for session type
        
        Args:
            tool_name: Name of the tool
            session_type: Type of session (main, group, sandbox)
            source: Source of request (bot, userbot)
        
        Returns:
            PermissionResult with allowed status and reason
        """
        # Determine effective session type
        effective_type = self._get_effective_type(session_type, source)
        
        config = self.permissions.get(effective_type, self.permissions["main"])
        mode = config.get("mode", "allowlist")
        tools = config.get("tools", "*")
        
        # Check based on mode
        if mode == "allowlist":
            if tools == "*":
                allowed = True
                reason = "All tools allowed"
            else:
                allowed = tool_name in tools
                reason = f"Tool {'in' if allowed else 'not in'} allowlist"
        
        elif mode == "denylist":
            if tools == "*":
                allowed = False
                reason = "All tools denied"
            else:
                allowed = tool_name not in tools
                reason = f"Tool {'not in' if allowed else 'in'} denylist"
        
        else:
            allowed = True
            reason = "Unknown mode, defaulting to allow"
        
        # Extra check for sandbox
        if effective_type == "sandbox" and tool_name in SANDBOX_DENIED:
            allowed = False
            reason = f"Tool '{tool_name}' never allowed in sandbox"
        
        return PermissionResult(
            allowed=allowed,
            reason=reason,
            tool=tool_name,
            session_type=effective_type
        )
    
    def _get_effective_type(self, session_type: str, source: str) -> str:
        """Determine effective session type"""
        # Userbot always uses userbot permissions
        if source == "userbot":
            return "userbot"
        
        # Map chat types to session types
        if session_type in ("private", "main"):
            return "main"
        elif session_type in ("group", "supergroup"):
            return "group"
        elif session_type == "sandbox":
            return "sandbox"
        
        return "main"
    
    def get_allowed_tools(self, session_type: str, source: str = "bot") -> list[str]:
        """Get list of allowed tools for session type"""
        effective_type = self._get_effective_type(session_type, source)
        config = self.permissions.get(effective_type, self.permissions["main"])
        mode = config.get("mode", "allowlist")
        tools = config.get("tools", "*")
        
        # Get all tool names
        from tools import TOOL_EXECUTORS
        all_tools = list(TOOL_EXECUTORS.keys())
        
        if mode == "allowlist":
            if tools == "*":
                allowed = all_tools
            else:
                allowed = [t for t in all_tools if t in tools]
        elif mode == "denylist":
            if tools == "*":
                allowed = []
            else:
                allowed = [t for t in all_tools if t not in tools]
        else:
            allowed = all_tools
        
        # Remove sandbox-denied tools
        if effective_type == "sandbox":
            allowed = [t for t in allowed if t not in SANDBOX_DENIED]
        
        return allowed
    
    def filter_tool_definitions(
        self, 
        definitions: list, 
        session_type: str,
        source: str = "bot"
    ) -> list:
        """Filter tool definitions based on permissions
        
        Use this to remove tools from LLM context that shouldn't be available
        """
        allowed = set(self.get_allowed_tools(session_type, source))
        
        filtered = []
        for tool_def in definitions:
            name = tool_def.get("function", {}).get("name", "")
            if name in allowed:
                filtered.append(tool_def)
        
        logger.debug(f"Filtered tools for {session_type}/{source}: {len(filtered)}/{len(definitions)}")
        return filtered
    
    def get_status(self) -> dict:
        """Get permissions status for admin panel"""
        from tools import TOOL_EXECUTORS
        all_tools = list(TOOL_EXECUTORS.keys())
        
        return {
            "session_types": list(self.permissions.keys()),
            "total_tools": len(all_tools),
            "permissions": {
                st: {
                    "mode": config.get("mode"),
                    "tools": config.get("tools"),
                    "allowed_count": len(self.get_allowed_tools(st)),
                    "description": config.get("description", "")
                }
                for st, config in self.permissions.items()
            },
            "dangerous_tools": DANGEROUS_TOOLS,
            "sandbox_denied": list(SANDBOX_DENIED),
        }
    
    def update_permission(
        self, 
        session_type: str, 
        mode: str = None,
        tools: list = None
    ) -> tuple[bool, str]:
        """Update permission config (for admin panel)"""
        if session_type not in self.permissions:
            self.permissions[session_type] = {"mode": "allowlist", "tools": "*"}
        
        if mode:
            if mode not in ("allowlist", "denylist"):
                return False, f"Invalid mode: {mode}"
            self.permissions[session_type]["mode"] = mode
        
        if tools is not None:
            self.permissions[session_type]["tools"] = tools
        
        # Save to file
        try:
            perm_file = Path("/workspace/_shared/tool_permissions.json")
            perm_file.parent.mkdir(parents=True, exist_ok=True)
            perm_file.write_text(json.dumps(self.permissions, indent=2))
            logger.info(f"Saved permissions to {perm_file}")
            return True, f"Updated {session_type} permissions"
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")
            return False, str(e)


# Global instance
tool_permissions = ToolPermissions()


def check_tool_permission(
    tool_name: str, 
    session_type: str = "main",
    source: str = "bot"
) -> PermissionResult:
    """Convenience function to check permission"""
    return tool_permissions.check_permission(tool_name, session_type, source)


def filter_tools_for_session(
    definitions: list,
    session_type: str,
    source: str = "bot"
) -> list:
    """Convenience function to filter tools"""
    return tool_permissions.filter_tool_definitions(definitions, session_type, source)
