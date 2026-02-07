"""
Tools API - Single source of truth for agent tools
Provides tool definitions, MCP server management, Skills, and dynamic tool loading
"""

import os
import json
import asyncio
import httpx
import glob
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import datetime

app = FastAPI(title="Tools API", version="3.0")

# Config files
CONFIG_FILE = "/data/tools_config.json"
MCP_CONFIG_FILE = "/data/mcp_servers.json"
MCP_TOOLS_CACHE = "/data/mcp_tools_cache.json"
SKILLS_CACHE = "/data/skills_cache.json"

# Workspace paths (mounted volume)
WORKSPACE_ROOT = os.environ.get("WORKSPACE_ROOT", "/workspace")
SHARED_SKILLS_DIR = "/data/skills"  # Global skills directory

# ============ BUILT-IN TOOLS ============

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
        "description": "Schedule reminders or recurring tasks.",
        "source": "builtin",
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
    # NEW: Tool for searching available tools
    "search_tools": {
        "enabled": True,
        "name": "search_tools",
        "description": "Search available tools by name or description. Use to discover what tools are available.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (matches name or description)"},
                "source": {"type": "string", "enum": ["all", "builtin", "mcp"], "description": "Filter by source"}
            },
            "required": []
        }
    }
}

# Bot-only tools (not managed by this API, always available for bot)
BOT_ONLY_TOOLS = ["send_file", "send_dm", "manage_message", "ask_user"]


# ============ MCP SUPPORT ============

class MCPServer(BaseModel):
    """MCP Server configuration"""
    name: str
    url: str  # e.g. http://localhost:3001 or stdio://path/to/server
    enabled: bool = True
    transport: str = "http"  # http, stdio, sse
    api_key: Optional[str] = None
    description: Optional[str] = None


class MCPToolsCache:
    """Cache for tools loaded from MCP servers"""
    
    def __init__(self):
        self.tools: Dict[str, dict] = {}
        self.last_refresh: Optional[datetime] = None
        self.server_status: Dict[str, dict] = {}
    
    def load_cache(self):
        """Load cached tools from file"""
        if os.path.exists(MCP_TOOLS_CACHE):
            try:
                with open(MCP_TOOLS_CACHE) as f:
                    data = json.load(f)
                    self.tools = data.get("tools", {})
                    self.last_refresh = datetime.fromisoformat(data["last_refresh"]) if data.get("last_refresh") else None
                    self.server_status = data.get("server_status", {})
            except:
                pass
    
    def save_cache(self):
        """Save tools cache to file"""
        os.makedirs(os.path.dirname(MCP_TOOLS_CACHE), exist_ok=True)
        with open(MCP_TOOLS_CACHE, 'w') as f:
            json.dump({
                "tools": self.tools,
                "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
                "server_status": self.server_status
            }, f, indent=2)
    
    def add_tools(self, server_name: str, tools: List[dict]):
        """Add tools from an MCP server"""
        for tool in tools:
            tool_name = f"mcp_{server_name}_{tool['name']}"
            self.tools[tool_name] = {
                "name": tool_name,
                "original_name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", tool.get("parameters", {})),
                "source": f"mcp:{server_name}",
                "server": server_name,
                "enabled": True
            }
        self.last_refresh = datetime.now()
        self.save_cache()
    
    def clear_server_tools(self, server_name: str):
        """Remove all tools from a specific server"""
        to_remove = [name for name, tool in self.tools.items() if tool.get("server") == server_name]
        for name in to_remove:
            del self.tools[name]
        self.save_cache()


# Global MCP cache
mcp_cache = MCPToolsCache()


# ============ SKILLS SUPPORT ============

class Skill(BaseModel):
    """Skill definition - like Anthropic's Skills"""
    name: str
    description: str
    version: str = "1.0"
    author: Optional[str] = None
    
    # Skill can provide:
    tools: List[dict] = []           # Custom tools
    system_prompt: Optional[str] = None  # Additional system prompt
    resources: List[str] = []        # Files/URLs to include in context
    commands: Dict[str, str] = {}    # Slash commands
    
    # Metadata
    enabled: bool = True
    source: str = "user"  # user, shared, marketplace
    path: Optional[str] = None


class SkillsManager:
    """Manages skills loaded from user workspaces and shared directory"""
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self.skill_tools: Dict[str, dict] = {}  # Flattened tools from all skills
        self.last_scan: Optional[datetime] = None
    
    def load_cache(self):
        """Load skills cache from file"""
        if os.path.exists(SKILLS_CACHE):
            try:
                with open(SKILLS_CACHE) as f:
                    data = json.load(f)
                    for name, skill_data in data.get("skills", {}).items():
                        self.skills[name] = Skill(**skill_data)
                    self.skill_tools = data.get("skill_tools", {})
                    self.last_scan = datetime.fromisoformat(data["last_scan"]) if data.get("last_scan") else None
            except Exception as e:
                print(f"Error loading skills cache: {e}")
    
    def save_cache(self):
        """Save skills cache to file"""
        os.makedirs(os.path.dirname(SKILLS_CACHE), exist_ok=True)
        with open(SKILLS_CACHE, 'w') as f:
            json.dump({
                "skills": {name: skill.dict() for name, skill in self.skills.items()},
                "skill_tools": self.skill_tools,
                "last_scan": self.last_scan.isoformat() if self.last_scan else None
            }, f, indent=2)
    
    def scan_directory(self, directory: str, source: str = "user") -> List[Skill]:
        """Scan directory for skill.json files"""
        found_skills = []
        
        if not os.path.exists(directory):
            return found_skills
        
        # Look for skill.json in immediate subdirectories
        for item in os.listdir(directory):
            skill_dir = os.path.join(directory, item)
            skill_file = os.path.join(skill_dir, "skill.json")
            
            if os.path.isdir(skill_dir) and os.path.exists(skill_file):
                try:
                    with open(skill_file) as f:
                        data = json.load(f)
                        skill = Skill(
                            name=data.get("name", item),
                            description=data.get("description", ""),
                            version=data.get("version", "1.0"),
                            author=data.get("author"),
                            tools=data.get("tools", []),
                            system_prompt=data.get("system_prompt"),
                            resources=data.get("resources", []),
                            commands=data.get("commands", {}),
                            enabled=data.get("enabled", True),
                            source=source,
                            path=skill_dir
                        )
                        found_skills.append(skill)
                except Exception as e:
                    print(f"Error loading skill from {skill_file}: {e}")
        
        return found_skills
    
    def scan_user_workspace(self, user_id: str) -> List[Skill]:
        """Scan user's workspace for skills"""
        user_skills_dir = os.path.join(WORKSPACE_ROOT, user_id, "skills")
        return self.scan_directory(user_skills_dir, source=f"user:{user_id}")
    
    def scan_shared_skills(self) -> List[Skill]:
        """Scan shared skills directory"""
        return self.scan_directory(SHARED_SKILLS_DIR, source="shared")
    
    def scan_all(self, user_id: Optional[str] = None):
        """Scan all skill sources and update cache"""
        self.skills.clear()
        self.skill_tools.clear()
        
        # 1. Load shared skills
        for skill in self.scan_shared_skills():
            self.skills[f"shared:{skill.name}"] = skill
        
        # 2. Load user skills (if user_id provided)
        if user_id:
            for skill in self.scan_user_workspace(user_id):
                self.skills[f"user:{skill.name}"] = skill
        
        # 3. Flatten tools from all enabled skills
        for skill_key, skill in self.skills.items():
            if skill.enabled:
                for tool in skill.tools:
                    tool_name = f"skill_{skill.name}_{tool['name']}"
                    self.skill_tools[tool_name] = {
                        "name": tool_name,
                        "original_name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                        "source": f"skill:{skill.name}",
                        "skill": skill.name,
                        "enabled": True
                    }
        
        self.last_scan = datetime.now()
        self.save_cache()
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get skill by name"""
        # Try exact match first
        if name in self.skills:
            return self.skills[name]
        # Try without prefix
        for key, skill in self.skills.items():
            if skill.name == name:
                return skill
        return None
    
    def get_enabled_tools(self) -> Dict[str, dict]:
        """Get all enabled tools from skills"""
        return {name: tool for name, tool in self.skill_tools.items() if tool.get("enabled", True)}
    
    def get_system_prompts(self) -> List[str]:
        """Get all system prompts from enabled skills"""
        prompts = []
        for skill in self.skills.values():
            if skill.enabled and skill.system_prompt:
                prompts.append(f"# Skill: {skill.name}\n{skill.system_prompt}")
        return prompts


# Global skills manager
skills_manager = SkillsManager()


def load_mcp_config() -> Dict[str, MCPServer]:
    """Load MCP server configurations"""
    if os.path.exists(MCP_CONFIG_FILE):
        try:
            with open(MCP_CONFIG_FILE) as f:
                data = json.load(f)
                return {name: MCPServer(**server) for name, server in data.items()}
        except:
            pass
    return {}


def save_mcp_config(servers: Dict[str, MCPServer]):
    """Save MCP server configurations"""
    os.makedirs(os.path.dirname(MCP_CONFIG_FILE), exist_ok=True)
    with open(MCP_CONFIG_FILE, 'w') as f:
        json.dump({name: server.dict() for name, server in servers.items()}, f, indent=2)


async def fetch_mcp_tools(server: MCPServer) -> List[dict]:
    """Fetch tools from an MCP server"""
    if server.transport == "http":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {}
                if server.api_key:
                    headers["Authorization"] = f"Bearer {server.api_key}"
                
                # MCP uses JSON-RPC 2.0
                response = await client.post(
                    f"{server.url}",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {}
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and "tools" in data["result"]:
                        return data["result"]["tools"]
                    # Fallback for non-standard MCP servers
                    if "tools" in data:
                        return data["tools"]
        except Exception as e:
            print(f"Error fetching tools from {server.name}: {e}")
    
    return []


async def call_mcp_tool(server: MCPServer, tool_name: str, arguments: dict) -> dict:
    """Call a tool on an MCP server"""
    if server.transport == "http":
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {}
                if server.api_key:
                    headers["Authorization"] = f"Bearer {server.api_key}"
                
                response = await client.post(
                    f"{server.url}",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        }
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        return {"success": True, "result": data["result"]}
                    if "error" in data:
                        return {"success": False, "error": data["error"]}
                
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    return {"success": False, "error": f"Unsupported transport: {server.transport}"}


# ============ TOOL CONFIG ============

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


def get_all_tools_with_state(user_id: Optional[str] = None) -> dict:
    """Get all tools (builtin + MCP + Skills) with their enabled/disabled state"""
    config = load_config()
    tools = {}
    
    # Built-in tools
    for name, tool in SHARED_TOOLS.items():
        enabled = config.get(name, {}).get("enabled", tool["enabled"])
        tools[name] = {
            **tool,
            "enabled": enabled
        }
    
    # MCP tools from cache
    mcp_cache.load_cache()
    for name, tool in mcp_cache.tools.items():
        enabled = config.get(name, {}).get("enabled", tool.get("enabled", True))
        tools[name] = {
            **tool,
            "enabled": enabled
        }
    
    # Skills tools (scan on each call for freshness)
    skills_manager.scan_all(user_id)
    for name, tool in skills_manager.get_enabled_tools().items():
        enabled = config.get(name, {}).get("enabled", tool.get("enabled", True))
        tools[name] = {
            **tool,
            "enabled": enabled
        }
    
    return tools


# ============ API ENDPOINTS ============

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "mcp_enabled": True}


@app.get("/tools")
async def get_all_tools(user_id: Optional[str] = None):
    """Get all tools with their definitions and state"""
    tools = get_all_tools_with_state(user_id)
    
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


@app.get("/tools/enabled")
async def get_enabled_tools(user_id: Optional[str] = None):
    """Get only enabled tools in OpenAI format (for agent)
    
    Pass user_id to include user-specific skills from their workspace.
    Tools are refreshed on each call to pick up new skills.
    """
    tools = get_all_tools_with_state(user_id)
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


@app.get("/tools/search")
async def search_tools(query: str = "", source: str = "all"):
    """Search tools by name or description"""
    tools = get_all_tools_with_state()
    results = []
    
    query_lower = query.lower()
    
    for tool in tools.values():
        # Filter by source
        if source == "builtin" and tool.get("source") != "builtin":
            continue
        if source == "mcp" and not tool.get("source", "").startswith("mcp:"):
            continue
        
        # Search in name and description
        if not query or query_lower in tool["name"].lower() or query_lower in tool.get("description", "").lower():
            results.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "source": tool.get("source", "builtin"),
                "enabled": tool["enabled"]
            })
    
    return {"results": results, "count": len(results)}


@app.get("/tools/{name}")
async def get_tool(name: str):
    """Get single tool definition"""
    tools = get_all_tools_with_state()
    if name not in tools:
        raise HTTPException(404, f"Tool {name} not found")
    return tools[name]


class ToolToggle(BaseModel):
    enabled: bool


@app.put("/tools/{name}")
async def toggle_tool(name: str, data: ToolToggle):
    """Enable/disable a tool"""
    tools = get_all_tools_with_state()
    
    if name not in tools:
        if name in BOT_ONLY_TOOLS:
            raise HTTPException(400, f"Tool {name} is bot-only and cannot be toggled here")
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name not in config:
        config[name] = {}
    config[name]["enabled"] = data.enabled
    save_config(config)
    
    return {"success": True, "name": name, "enabled": data.enabled}


@app.post("/tools/{name}/reset")
async def reset_tool(name: str):
    """Reset tool to default state"""
    tools = get_all_tools_with_state()
    
    if name not in tools:
        raise HTTPException(404, f"Tool {name} not found")
    
    config = load_config()
    if name in config:
        del config[name]
        save_config(config)
    
    return {"success": True, "name": name}


# ============ MCP SERVER MANAGEMENT ============

@app.get("/mcp/servers")
async def list_mcp_servers():
    """List all configured MCP servers"""
    servers = load_mcp_config()
    mcp_cache.load_cache()
    
    result = []
    for name, server in servers.items():
        tool_count = len([t for t in mcp_cache.tools.values() if t.get("server") == name])
        result.append({
            **server.dict(),
            "tool_count": tool_count,
            "status": mcp_cache.server_status.get(name, {})
        })
    
    return {"servers": result}


class MCPServerCreate(BaseModel):
    name: str
    url: str
    transport: str = "http"
    api_key: Optional[str] = None
    description: Optional[str] = None


@app.post("/mcp/servers")
async def add_mcp_server(data: MCPServerCreate):
    """Add a new MCP server"""
    servers = load_mcp_config()
    
    if data.name in servers:
        raise HTTPException(400, f"Server {data.name} already exists")
    
    server = MCPServer(
        name=data.name,
        url=data.url,
        transport=data.transport,
        api_key=data.api_key,
        description=data.description
    )
    
    servers[data.name] = server
    save_mcp_config(servers)
    
    # Try to fetch tools immediately
    tools = await fetch_mcp_tools(server)
    if tools:
        mcp_cache.add_tools(data.name, tools)
        mcp_cache.server_status[data.name] = {"connected": True, "tool_count": len(tools)}
    else:
        mcp_cache.server_status[data.name] = {"connected": False, "error": "Failed to fetch tools"}
    mcp_cache.save_cache()
    
    return {"success": True, "name": data.name, "tools_loaded": len(tools)}


@app.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove an MCP server"""
    servers = load_mcp_config()
    
    if name not in servers:
        raise HTTPException(404, f"Server {name} not found")
    
    del servers[name]
    save_mcp_config(servers)
    
    # Remove cached tools
    mcp_cache.clear_server_tools(name)
    if name in mcp_cache.server_status:
        del mcp_cache.server_status[name]
    mcp_cache.save_cache()
    
    return {"success": True, "name": name}


@app.post("/mcp/servers/{name}/refresh")
async def refresh_mcp_server(name: str):
    """Refresh tools from an MCP server"""
    servers = load_mcp_config()
    
    if name not in servers:
        raise HTTPException(404, f"Server {name} not found")
    
    server = servers[name]
    
    # Clear old tools
    mcp_cache.clear_server_tools(name)
    
    # Fetch new tools
    tools = await fetch_mcp_tools(server)
    if tools:
        mcp_cache.add_tools(name, tools)
        mcp_cache.server_status[name] = {"connected": True, "tool_count": len(tools), "last_refresh": datetime.now().isoformat()}
    else:
        mcp_cache.server_status[name] = {"connected": False, "error": "Failed to fetch tools"}
    mcp_cache.save_cache()
    
    return {"success": True, "name": name, "tools_loaded": len(tools)}


@app.post("/mcp/refresh-all")
async def refresh_all_mcp_servers():
    """Refresh tools from all MCP servers"""
    servers = load_mcp_config()
    results = {}
    
    for name, server in servers.items():
        if server.enabled:
            mcp_cache.clear_server_tools(name)
            tools = await fetch_mcp_tools(server)
            if tools:
                mcp_cache.add_tools(name, tools)
                mcp_cache.server_status[name] = {"connected": True, "tool_count": len(tools)}
                results[name] = {"success": True, "tools": len(tools)}
            else:
                mcp_cache.server_status[name] = {"connected": False}
                results[name] = {"success": False, "error": "Failed to fetch tools"}
    
    mcp_cache.save_cache()
    
    return {"results": results}


@app.post("/mcp/call/{server_name}/{tool_name}")
async def call_mcp_tool_endpoint(server_name: str, tool_name: str, arguments: dict = {}):
    """Call a tool on an MCP server"""
    servers = load_mcp_config()
    
    if server_name not in servers:
        raise HTTPException(404, f"Server {server_name} not found")
    
    server = servers[server_name]
    result = await call_mcp_tool(server, tool_name, arguments)
    
    return result


# ============ SKILLS MANAGEMENT ============

@app.get("/skills")
async def list_skills(user_id: Optional[str] = None):
    """List all available skills"""
    skills_manager.scan_all(user_id)
    
    skills_list = []
    for key, skill in skills_manager.skills.items():
        tool_count = len([t for t in skills_manager.skill_tools.values() if t.get("skill") == skill.name])
        skills_list.append({
            "key": key,
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "author": skill.author,
            "source": skill.source,
            "enabled": skill.enabled,
            "tool_count": tool_count,
            "has_system_prompt": bool(skill.system_prompt),
            "commands": list(skill.commands.keys()) if skill.commands else [],
            "path": skill.path
        })
    
    return {
        "skills": skills_list,
        "total": len(skills_list),
        "last_scan": skills_manager.last_scan.isoformat() if skills_manager.last_scan else None
    }


@app.get("/skills/{name}")
async def get_skill(name: str, user_id: Optional[str] = None):
    """Get skill details"""
    skills_manager.scan_all(user_id)
    skill = skills_manager.get_skill(name)
    
    if not skill:
        raise HTTPException(404, f"Skill {name} not found")
    
    # Get tools from this skill
    skill_tools = [t for t in skills_manager.skill_tools.values() if t.get("skill") == skill.name]
    
    return {
        "skill": skill.dict(),
        "tools": skill_tools
    }


@app.post("/skills/scan")
async def scan_skills(user_id: Optional[str] = None):
    """Force rescan of all skills"""
    skills_manager.scan_all(user_id)
    
    return {
        "success": True,
        "skills_found": len(skills_manager.skills),
        "tools_loaded": len(skills_manager.skill_tools),
        "last_scan": skills_manager.last_scan.isoformat() if skills_manager.last_scan else None
    }


@app.get("/skills/{name}/prompt")
async def get_skill_prompt(name: str, user_id: Optional[str] = None):
    """Get system prompt from a skill"""
    skills_manager.scan_all(user_id)
    skill = skills_manager.get_skill(name)
    
    if not skill:
        raise HTTPException(404, f"Skill {name} not found")
    
    return {
        "name": skill.name,
        "system_prompt": skill.system_prompt
    }


@app.get("/skills/prompts/all")
async def get_all_skill_prompts(user_id: Optional[str] = None):
    """Get all system prompts from enabled skills"""
    skills_manager.scan_all(user_id)
    prompts = skills_manager.get_system_prompts()
    
    return {
        "prompts": prompts,
        "count": len(prompts)
    }


class SkillToggle(BaseModel):
    enabled: bool


@app.put("/skills/{name}")
async def toggle_skill(name: str, data: SkillToggle, user_id: Optional[str] = None):
    """Enable/disable a skill"""
    skills_manager.scan_all(user_id)
    skill = skills_manager.get_skill(name)
    
    if not skill:
        raise HTTPException(404, f"Skill {name} not found")
    
    # Update enabled state (this will be lost on next scan, need persistent config)
    skill.enabled = data.enabled
    skills_manager.save_cache()
    
    return {"success": True, "name": name, "enabled": data.enabled}


# ============ STARTUP ============

@app.on_event("startup")
async def startup():
    """Load caches on startup"""
    mcp_cache.load_cache()
    skills_manager.load_cache()
    print(f"Loaded {len(mcp_cache.tools)} MCP tools from cache")
    print(f"Loaded {len(skills_manager.skills)} skills from cache")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
