"""Tools API routes"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..tools import get_all_tools as get_builtin_tools, BOT_ONLY_TOOLS
from ..mcp import mcp_cache
from ..skills import skills_manager
from ..config import load_config, save_config, get_all_tools_with_state

router = APIRouter(tags=["tools"])


@router.get("/tools")
async def list_all_tools(user_id: Optional[str] = None):
    """Get all tools with their definitions and state"""
    shared_tools = get_builtin_tools()
    tools = get_all_tools_with_state(shared_tools, mcp_cache, skills_manager, user_id)
    
    builtin_count = len([t for t in tools.values() if t.get("source") == "builtin"])
    mcp_count = len([t for t in tools.values() if t.get("source", "").startswith("mcp:")])
    skill_count = len([t for t in tools.values() if t.get("source", "").startswith("skill:")])
    
    return {
        "tools": list(tools.values()),
        "bot_only_tools": BOT_ONLY_TOOLS,
        "stats": {
            "builtin": builtin_count,
            "mcp": mcp_count,
            "skill": skill_count,
            "total": len(tools)
        }
    }


@router.get("/tools/enabled")
async def get_enabled_tools(user_id: Optional[str] = None):
    """Get only enabled tools in OpenAI format (for agent)
    
    Pass user_id to include user-specific skills from their workspace.
    Tools are refreshed on each call to pick up new skills.
    """
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, user_id)
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


@router.get("/tools/search")
async def search_tools(query: str = "", source: str = "all", limit: int = 10):
    """Search tools by name or description with FTS scoring
    
    Returns tools sorted by relevance score:
    - Exact name match: +100
    - Name contains query: +50
    - Description contains query: +10
    """
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, None)
    results = []
    
    query_lower = query.lower().strip()
    query_words = query_lower.split() if query_lower else []
    
    for tool in tools.values():
        # Filter by source
        if source != "all":
            tool_source = tool.get("source", "builtin")
            if source == "builtin" and not tool_source.startswith("builtin"):
                continue
            if source == "mcp" and not tool_source.startswith("mcp:"):
                continue
            if source == "skill" and not tool_source.startswith("skill:"):
                continue
        
        # Calculate relevance score
        if not query_lower:
            score = 0
        else:
            score = 0
            name_lower = tool["name"].lower()
            desc_lower = tool.get("description", "").lower()
            
            # Exact name match
            if name_lower == query_lower:
                score += 100
            # Name contains full query
            elif query_lower in name_lower:
                score += 50
            # Name contains any word
            elif any(word in name_lower for word in query_words):
                score += 30
            
            # Description contains full query
            if query_lower in desc_lower:
                score += 10
            # Description contains any word
            elif any(word in desc_lower for word in query_words):
                score += 5
            
            # Skip if no match
            if score == 0:
                continue
        
        results.append({
            **tool,
            "_score": score
        })
    
    # Sort by score (descending), then by name
    results.sort(key=lambda x: (-x.get("_score", 0), x["name"]))
    
    # Apply limit
    if limit > 0:
        results = results[:limit]
    
    # Format for agent consumption
    formatted = []
    for tool in results:
        formatted.append({
            "name": tool["name"],
            "description": tool.get("description", ""),
            "source": tool.get("source", "builtin"),
            "score": tool.get("_score", 0)
        })
    
    return {"tools": formatted, "count": len(formatted), "total_available": len(tools)}


@router.get("/tools/base")
async def get_base_tools():
    """Get only base tools for lazy loading
    
    Returns minimal set of tools that agent always has:
    - Core file operations
    - Memory
    - search_tools + load_tools (to discover and load more)
    - manage_tasks
    """
    BASE_TOOL_NAMES = [
        "run_command", "read_file", "write_file", "edit_file",
        "list_directory", "search_files", "search_text",
        "memory", "manage_tasks", 
        "search_tools", "load_tools",  # Tool discovery
        # Web and Telegram
        "search_web", "fetch_page",
        "telegram_channel", "telegram_send", "telegram_dialogs",
        "telegram_history", "telegram_join"
    ]
    
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, None)
    base_tools = []
    
    for name in BASE_TOOL_NAMES:
        if name in tools and tools[name].get("enabled", True):
            tool = tools[name]
            base_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
    
    return {"tools": base_tools, "count": len(base_tools)}


@router.post("/tools/load")
async def load_toolkit(names: list[str]):
    """Load specific tools by name
    
    Agent calls this after search_tools to get full definitions
    of tools it wants to use.
    """
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, None)
    loaded = []
    not_found = []
    
    for name in names:
        if name in tools and tools[name].get("enabled", True):
            tool = tools[name]
            loaded.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        else:
            not_found.append(name)
    
    return {
        "tools": loaded, 
        "count": len(loaded),
        "not_found": not_found
    }


@router.get("/tools/{name}")
async def get_tool(name: str):
    """Get specific tool definition"""
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, None)
    if name in tools:
        return tools[name]
    raise HTTPException(404, f"Tool {name} not found")


class ToolToggle(BaseModel):
    enabled: bool


@router.put("/tools/{name}")
async def toggle_tool(name: str, data: ToolToggle):
    """Enable or disable a tool"""
    tools = get_all_tools_with_state(get_builtin_tools(), mcp_cache, skills_manager, None)
    
    if name not in tools:
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name not in config:
        config[name] = {}
    config[name]["enabled"] = data.enabled
    save_config(config)
    
    return {"success": True, "name": name, "enabled": data.enabled}


@router.delete("/tools/{name}")
async def reset_tool(name: str):
    """Reset tool to default state"""
    config = load_config()
    
    if name in config:
        del config[name]
        save_config(config)
    
    return {"success": True, "name": name, "message": "Reset to default"}
