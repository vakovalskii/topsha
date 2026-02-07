"""Tool registry and common types"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from typing import Callable, Any
from logger import log_tool_call, log_tool_result
from config import CONFIG
from models import ToolResult, ToolContext


# Tool definitions for OpenAI
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command. Use for: git, npm, pip, python, system ops.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file within workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files by glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List directory contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet for current info, news, docs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch and parse URL content as markdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
        }
    },
    {
        "type": "function",
        "function": {
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
    },
    {
        "type": "function",
        "function": {
            "name": "send_file",
            "description": "Send a file from workspace to the chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to file in workspace"},
                    "caption": {"type": "string", "description": "Optional caption"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_dm",
            "description": "Send a private message to current user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "User ID (usually current user)"},
                    "text": {"type": "string", "description": "Message text"}
                },
                "required": ["user_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_message",
            "description": "Edit or delete bot messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["edit", "delete"]},
                    "message_id": {"type": "integer", "description": "Message ID to edit/delete"},
                    "text": {"type": "string", "description": "New text (for edit)"}
                },
                "required": ["action", "message_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask user a question and wait for their answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask"},
                    "timeout": {"type": "integer", "description": "Seconds to wait (default 60)"}
                },
                "required": ["question"]
            }
        }
    }
]


# Import tool executors (done after class definitions to avoid circular imports)
from tools.bash import tool_run_command
from tools.files import tool_read_file, tool_write_file, tool_edit_file, tool_delete_file, tool_search_files, tool_search_text, tool_list_directory
from tools.web import tool_search_web, tool_fetch_page
from tools.memory import tool_memory
from tools.scheduler import tool_schedule_task
from tools.tasks import tool_manage_tasks
from tools.send_file import tool_send_file
from tools.send_dm import tool_send_dm
from tools.message import tool_manage_message
from tools.ask_user import tool_ask_user
from tools.permissions import check_tool_permission, filter_tools_for_session
from tools.telegram import (
    tool_telegram_channel, tool_telegram_join, tool_telegram_send,
    tool_telegram_history, tool_telegram_dialogs, tool_telegram_delete,
    tool_telegram_edit, tool_telegram_resolve
)


# Tool discovery - for lazy loading
async def tool_search_tools(args: dict, ctx: ToolContext) -> ToolResult:
    """Search available tools by name or description"""
    import aiohttp
    
    query = args.get("query", "")
    source = args.get("source", "all")
    limit = args.get("limit", 10)
    
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{tools_api_url}/tools/search",
                params={"query": query, "source": source, "limit": limit}
            ) as resp:
                data = await resp.json()
        
        tools = data.get("tools", [])
        total = data.get("total_available", 0)
        
        if not tools:
            return ToolResult(True, output=f"No tools found for '{query}'. Total available: {total}")
        
        lines = [f"## Found {len(tools)} tools (of {total} total)\n"]
        
        for tool in tools:
            score = tool.get("score", 0)
            source_tag = f"[{tool.get('source', 'builtin')}]" if tool.get('source') != 'builtin' else ""
            lines.append(f"• **{tool['name']}** {source_tag}")
            lines.append(f"  {tool.get('description', 'No description')[:100]}")
            if score > 0:
                lines.append(f"  _relevance: {score}_")
            lines.append("")
        
        lines.append("\n💡 Use `load_tools` to add these to your current session.")
        
        return ToolResult(True, output="\n".join(lines))
    except Exception as e:
        return ToolResult(False, error=f"Failed to search tools: {e}")


async def tool_load_tools(args: dict, ctx: ToolContext) -> ToolResult:
    """Load additional tools by name into current session"""
    import aiohttp
    
    names = args.get("names", [])
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",")]
    
    if not names:
        return ToolResult(False, error="Provide tool names to load")
    
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{tools_api_url}/tools/load",
                json=names
            ) as resp:
                data = await resp.json()
        
        loaded = data.get("tools", [])
        not_found = data.get("not_found", [])
        
        if loaded:
            # Store loaded tools in context for this session
            # The agent will pick these up on next iteration
            loaded_names = [t["function"]["name"] for t in loaded]
            output = f"✅ Loaded {len(loaded)} tools: {', '.join(loaded_names)}"
            if not_found:
                output += f"\n⚠️ Not found: {', '.join(not_found)}"
            return ToolResult(True, output=output, metadata={"loaded_tools": loaded})
        else:
            return ToolResult(False, error=f"No tools loaded. Not found: {', '.join(not_found)}")
    except Exception as e:
        return ToolResult(False, error=f"Failed to load tools: {e}")


# Skill management tools
async def tool_install_skill(args: dict, ctx: ToolContext) -> ToolResult:
    """Install a skill from Anthropic's repository"""
    import aiohttp
    
    name = args.get("name", "").lower()
    source = args.get("source", "anthropic")
    
    if not name:
        return ToolResult(False, error="Skill name required")
    
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{tools_api_url}/skills/install",
                json={"name": name, "source": source},
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return ToolResult(True, output=f"✅ {data.get('message', 'Installed')}\nPath: {data.get('path', '')}")
                else:
                    return ToolResult(False, error=data.get("detail", "Installation failed"))
    except Exception as e:
        return ToolResult(False, error=f"Failed to install skill: {e}")


async def tool_list_skills(args: dict, ctx: ToolContext) -> ToolResult:
    """List available and installed skills"""
    import aiohttp
    
    installed_only = args.get("installed_only", False)
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get installed skills
            async with session.get(f"{tools_api_url}/skills") as resp:
                installed_data = await resp.json()
            
            # Get available skills
            async with session.get(f"{tools_api_url}/skills/available") as resp:
                available_data = await resp.json()
        
        lines = ["## Skills\n"]
        
        if not installed_only:
            lines.append("### Available for Installation")
            lines.append("| Skill | Description | Status |")
            lines.append("|-------|-------------|--------|")
            for skill in available_data.get("available", []):
                status = "✅ Installed" if skill["installed"] else "📦 Available"
                lines.append(f"| `{skill['name']}` | {skill['description'][:50]}... | {status} |")
            lines.append("")
        
        lines.append("### Installed Skills")
        installed = installed_data.get("skills", [])
        if installed:
            lines.append("| Skill | Description | Path |")
            lines.append("|-------|-------------|------|")
            for skill in installed:
                lines.append(f"| `{skill['name']}` | {skill['description'][:40]}... | `{skill.get('path', '')}` |")
        else:
            lines.append("No skills installed yet. Use `install_skill` to add some!")
        
        return ToolResult(True, output="\n".join(lines))
    except Exception as e:
        return ToolResult(False, error=f"Failed to list skills: {e}")


# Tool registry
TOOL_EXECUTORS = {
    "run_command": tool_run_command,
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "edit_file": tool_edit_file,
    "delete_file": tool_delete_file,
    "search_files": tool_search_files,
    "search_text": tool_search_text,
    "list_directory": tool_list_directory,
    "search_web": tool_search_web,
    "fetch_page": tool_fetch_page,
    "memory": tool_memory,
    "schedule_task": tool_schedule_task,
    "manage_tasks": tool_manage_tasks,
    "send_file": tool_send_file,
    "send_dm": tool_send_dm,
    "manage_message": tool_manage_message,
    "ask_user": tool_ask_user,
    # Tool discovery (lazy loading)
    "search_tools": tool_search_tools,
    "load_tools": tool_load_tools,
    # Skill management
    "install_skill": tool_install_skill,
    "list_skills": tool_list_skills,
    # Telegram userbot tools
    "telegram_channel": tool_telegram_channel,
    "telegram_join": tool_telegram_join,
    "telegram_send": tool_telegram_send,
    "telegram_history": tool_telegram_history,
    "telegram_dialogs": tool_telegram_dialogs,
    "telegram_delete": tool_telegram_delete,
    "telegram_edit": tool_telegram_edit,
    "telegram_resolve": tool_telegram_resolve,
}


async def execute_tool(name: str, args: dict, ctx: ToolContext) -> ToolResult:
    """Execute a tool by name with permission check"""
    
    # Check tool permission based on session type
    perm = check_tool_permission(
        tool_name=name,
        session_type=ctx.chat_type,
        source=ctx.source
    )
    
    if not perm.allowed:
        log_tool_call(name, args)
        log_tool_result(False, None, f"PERMISSION DENIED: {perm.reason}")
        return ToolResult(
            False, 
            error=f"🔒 Tool '{name}' not available in {perm.session_type} sessions. {perm.reason}"
        )
    
    executor = TOOL_EXECUTORS.get(name)
    if not executor:
        return ToolResult(False, error=f"Unknown tool: {name}")
    
    log_tool_call(name, args)
    
    try:
        result = await asyncio.wait_for(
            executor(args, ctx),
            timeout=CONFIG.tool_timeout
        )
        
        log_tool_result(result.success, result.output, result.error)
        return result
        
    except asyncio.TimeoutError:
        return ToolResult(False, error=f"Tool {name} timed out")
    except Exception as e:
        return ToolResult(False, error=str(e))
