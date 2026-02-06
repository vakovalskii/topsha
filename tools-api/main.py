"""
Tools API - Single source of truth for agent tools
Provides tool definitions and enabled/disabled state
"""

import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Tools API", version="1.0")

# Config file for tool states
CONFIG_FILE = "/data/tools_config.json"

# These are SHARED tools managed by this API
# Bot-specific tools (send_file, send_dm, manage_message, ask_user) 
# are NOT here - they are hardcoded in core/tools/ and always available for bot

# SHARED tools - available to all agents, managed via admin panel
# Bot-specific tools (send_file, send_dm, manage_message, ask_user) are in core/tools/
SHARED_TOOLS = {
    "run_command": {
        "enabled": True,
        "name": "run_command",
        "description": "Run a shell command. Use for: git, npm, pip, python, system ops.",
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
        "description": "Schedule reminders or recurring tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "cancel"]},
                "type": {"type": "string", "enum": ["message", "command", "agent"]},
                "content": {"type": "string", "description": "Task content"},
                "delay_minutes": {"type": "integer", "description": "Delay before execution"},
                "recurring": {"type": "boolean", "description": "Repeat task"},
                "interval_minutes": {"type": "integer", "description": "Repeat interval"},
                "task_id": {"type": "string", "description": "Task ID for cancel"}
            },
            "required": ["action"]
        }
    },
    "manage_tasks": {
        "enabled": True,
        "name": "manage_tasks",
        "description": "Todo list for planning complex tasks.",
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
    }
}

# Bot-only tools (not managed by this API, always available for bot)
BOT_ONLY_TOOLS = ["send_file", "send_dm", "manage_message", "ask_user"]


def load_config() -> dict:
    """Load tool config from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(config: dict):
    """Save tool config to file"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_tools_with_state() -> dict:
    """Get all shared tools with their enabled/disabled state"""
    config = load_config()
    tools = {}
    
    for name, tool in SHARED_TOOLS.items():
        enabled = config.get(name, {}).get("enabled", tool["enabled"])
        tools[name] = {
            **tool,
            "enabled": enabled
        }
    
    return tools


# ============ API ENDPOINTS ============

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/tools")
async def get_all_tools():
    """Get all shared tools with their definitions and state"""
    tools = get_tools_with_state()
    return {"tools": list(tools.values()), "bot_only_tools": BOT_ONLY_TOOLS}


@app.get("/tools/enabled")
async def get_enabled_tools():
    """Get only enabled shared tools in OpenAI format (for agent)
    
    Note: Bot-specific tools (send_file, send_dm, etc.) are added by core agent
    """
    tools = get_tools_with_state()
    enabled = []
    
    for tool in tools.values():
        if tool["enabled"]:
            enabled.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
    
    return {"tools": enabled, "count": len(enabled)}


@app.get("/tools/{name}")
async def get_tool(name: str):
    """Get single tool definition"""
    tools = get_tools_with_state()
    if name not in tools:
        raise HTTPException(404, f"Tool {name} not found")
    return tools[name]


class ToolToggle(BaseModel):
    enabled: bool


@app.put("/tools/{name}")
async def toggle_tool(name: str, data: ToolToggle):
    """Enable/disable a shared tool"""
    if name not in SHARED_TOOLS:
        if name in BOT_ONLY_TOOLS:
            raise HTTPException(400, f"Tool {name} is bot-only and cannot be toggled here")
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name not in config:
        config[name] = {}
    config[name]["enabled"] = data.enabled
    save_config(config)
    
    return {"success": True, "name": name, "enabled": data.enabled}


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    enabled: Optional[bool] = None


@app.patch("/tools/{name}")
async def update_tool(name: str, data: ToolUpdate):
    """Update tool properties"""
    if name not in SHARED_TOOLS:
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name not in config:
        config[name] = {}
    
    if data.enabled is not None:
        config[name]["enabled"] = data.enabled
    if data.description is not None:
        config[name]["description"] = data.description
    
    save_config(config)
    
    return {"success": True, "name": name}


@app.post("/tools/{name}/reset")
async def reset_tool(name: str):
    """Reset tool to default state"""
    if name not in SHARED_TOOLS:
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name in config:
        del config[name]
        save_config(config)
    
    return {"success": True, "name": name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
