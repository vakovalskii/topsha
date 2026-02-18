"""MCP (Model Context Protocol) support"""

import os
import json
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

# Config paths
MCP_CONFIG_FILE = "/data/mcp_servers.json"
MCP_TOOLS_CACHE = "/data/mcp_tools_cache.json"


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
        json.dump({name: server.model_dump() for name, server in servers.items()}, f, indent=2)


async def fetch_mcp_tools(server: MCPServer) -> List[dict]:
    """Fetch tools from an MCP server"""
    if server.transport == "http":
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers = {
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json"
                }
                if server.api_key:
                    headers["Authorization"] = f"Bearer {server.api_key}"
                    print(f"[MCP {server.name}] requesting with Bearer auth")
                else:
                    print(f"[MCP {server.name}] requesting without auth (no token configured)")

                # Try Streamable HTTP MCP first (requires session)
                # Step 1: Initialize session
                init_response = await client.post(
                    server.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "topsha-tools-api", "version": "1.0"}
                        }
                    },
                    headers=headers
                )
                if init_response.status_code != 200:
                    print(f"[MCP {server.name}] initialize status={init_response.status_code} body={init_response.text[:500]}")
                session_id = init_response.headers.get("mcp-session-id")
                if not session_id and init_response.status_code == 200:
                    try:
                        init_body = init_response.json()
                        session_id = init_body.get("result", {}).get("sessionId") or init_body.get("sessionId")
                    except Exception:
                        pass
                if not session_id and init_response.status_code == 200:
                    print(f"[MCP {server.name}] initialize OK but no mcp-session-id (header or body), using legacy path")

                if session_id:
                    # Streamable HTTP MCP - use session ID
                    headers["mcp-session-id"] = session_id
                    response = await client.post(
                        server.url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/list",
                            "params": {}
                        },
                        headers=headers
                    )

                    if response.status_code == 200:
                        text = response.text.strip()
                        # Parse SSE: lines "data: { ... }"
                        for line in text.split("\n"):
                            s = line.strip()
                            if s.startswith("data:"):
                                payload = s[5:].strip()
                                if not payload:
                                    continue
                                try:
                                    data = json.loads(payload)
                                    if "result" in data and "tools" in data["result"]:
                                        return data["result"]["tools"]
                                except json.JSONDecodeError:
                                    pass
                        # Fallback: single JSON object (some streamable servers)
                        try:
                            data = json.loads(text)
                            if "result" in data and "tools" in data["result"]:
                                return data["result"]["tools"]
                            if "tools" in data:
                                return data["tools"]
                        except json.JSONDecodeError:
                            pass
                        print(f"[MCP {server.name}] tools/list SSE/JSON: no result.tools (len={len(text)}) preview: {text[:200]!r}")
                    else:
                        print(f"[MCP {server.name}] tools/list status={response.status_code} body={response.text[:500]}")
                else:
                    # Simple JSON-RPC (legacy MCP servers)
                    response = await client.post(
                        server.url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/list",
                            "params": {}
                        },
                        headers=headers
                    )

                    if response.status_code == 200:
                        raw = response.text
                        if not raw or not raw.strip():
                            print(f"[MCP {server.name}] tools/list empty response body")
                        else:
                            # Try plain JSON first (single JSON-RPC object)
                            try:
                                data = json.loads(raw)
                                if "result" in data and "tools" in data["result"]:
                                    return data["result"]["tools"]
                                if "tools" in data:
                                    return data["tools"]
                                if "error" in data:
                                    print(f"[MCP {server.name}] tools/list JSON-RPC error: {data['error']}")
                                else:
                                    print(f"[MCP {server.name}] tools/list unexpected JSON keys: {list(data.keys())[:10]}")
                            except json.JSONDecodeError:
                                # Maybe SSE format (one JSON per "data: " line)
                                for line in raw.split("\n"):
                                    if line.startswith("data: "):
                                        try:
                                            data = json.loads(line[6:])
                                            if "result" in data and "tools" in data["result"]:
                                                return data["result"]["tools"]
                                        except json.JSONDecodeError:
                                            pass
                                print(f"[MCP {server.name}] tools/list invalid JSON and no SSE data. body preview: {raw[:300]!r}")
                    else:
                        print(f"[MCP {server.name}] tools/list status={response.status_code} body={response.text[:500]}")
        except Exception as e:
            print(f"[MCP {server.name}] Error fetching tools: {e}")
    
    return []


async def call_mcp_tool(server: MCPServer, tool_name: str, arguments: dict) -> dict:
    """Call a tool on an MCP server"""
    if server.transport == "http":
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json"
                }
                if server.api_key:
                    headers["Authorization"] = f"Bearer {server.api_key}"
                
                # Step 1: Initialize session (for Streamable HTTP MCP)
                init_response = await client.post(
                    server.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "topsha-tools-api", "version": "1.0"}
                        }
                    },
                    headers=headers
                )
                
                session_id = init_response.headers.get("mcp-session-id")
                if session_id:
                    headers["mcp-session-id"] = session_id
                
                # Step 2: Call tool
                response = await client.post(
                    server.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": arguments
                        }
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    text = response.text
                    # Try SSE format first
                    for line in text.split('\n'):
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                if "result" in data:
                                    return {"success": True, "result": data["result"]}
                                if "error" in data:
                                    return {"success": False, "error": data["error"]}
                            except:
                                pass
                    # Try plain JSON
                    try:
                        data = response.json()
                        if "result" in data:
                            return {"success": True, "result": data["result"]}
                        if "error" in data:
                            return {"success": False, "error": data["error"]}
                    except:
                        pass
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    return {"success": False, "error": f"Unsupported transport: {server.transport}"}
