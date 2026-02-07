"""MCP server management routes"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..mcp import (
    MCPServer, mcp_cache,
    load_mcp_config, save_mcp_config,
    fetch_mcp_tools, call_mcp_tool
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers")
async def list_mcp_servers():
    """List all configured MCP servers"""
    servers = load_mcp_config()
    mcp_cache.load_cache()
    
    result = []
    for name, server in servers.items():
        result.append({
            **server.dict(),
            "tool_count": len([t for t in mcp_cache.tools.values() if t.get("server") == name]),
            "status": mcp_cache.server_status.get(name, {})
        })
    
    return {"servers": result}


class MCPServerCreate(BaseModel):
    name: str
    url: str
    transport: str = "http"
    api_key: Optional[str] = None
    description: Optional[str] = None


@router.post("/servers")
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
    
    return {"success": True, "name": data.name, "tools_loaded": len(tools) if tools else 0}


@router.delete("/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove an MCP server"""
    servers = load_mcp_config()
    
    if name not in servers:
        raise HTTPException(404, f"Server {name} not found")
    
    del servers[name]
    save_mcp_config(servers)
    
    # Clear cached tools
    mcp_cache.clear_server_tools(name)
    if name in mcp_cache.server_status:
        del mcp_cache.server_status[name]
    mcp_cache.save_cache()
    
    return {"success": True, "name": name}


class MCPServerToggle(BaseModel):
    enabled: bool


@router.put("/servers/{name}/toggle")
async def toggle_mcp_server(name: str, data: MCPServerToggle):
    """Enable or disable an MCP server"""
    servers = load_mcp_config()
    
    if name not in servers:
        raise HTTPException(404, f"Server {name} not found")
    
    servers[name].enabled = data.enabled
    save_mcp_config(servers)
    
    if data.enabled:
        # Refresh tools when enabling
        tools = await fetch_mcp_tools(servers[name])
        if tools:
            mcp_cache.add_tools(name, tools)
            mcp_cache.server_status[name] = {"connected": True, "tool_count": len(tools)}
    else:
        # Clear tools when disabling
        mcp_cache.clear_server_tools(name)
        mcp_cache.server_status[name] = {"connected": False, "disabled": True}
    
    mcp_cache.save_cache()
    
    return {"success": True, "name": name, "enabled": data.enabled}


@router.post("/servers/{name}/refresh")
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


@router.post("/refresh-all")
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


@router.post("/call/{server_name}/{tool_name}")
async def call_mcp_tool_endpoint(server_name: str, tool_name: str, arguments: dict = {}):
    """Call a tool on an MCP server"""
    servers = load_mcp_config()
    
    if server_name not in servers:
        raise HTTPException(404, f"Server {server_name} not found")
    
    server = servers[server_name]
    result = await call_mcp_tool(server, tool_name, arguments)
    
    return result
