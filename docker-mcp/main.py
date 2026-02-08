"""
Docker MCP Server - управление Docker через Model Context Protocol

Модульная архитектура:
- tools/          - каждый tool в отдельном файле (definition + executor)
- main.py         - FastAPI сервер + JSON-RPC endpoint

Tools загружаются автоматически из tools/*.py
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List
import docker
import json

# Import modular tools
from tools import get_tools, execute_tool

app = FastAPI(title="Docker MCP Server", version="2.0")

# Docker client for health check
client = docker.from_env()


# ============ Models ============

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int
    method: str
    params: Dict[str, Any] = {}


# ============ Endpoints ============

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        client.ping()
        tools = get_tools()
        return {
            "status": "ok",
            "docker": "connected",
            "tools_count": len(tools)
        }
    except Exception as e:
        return {"status": "error", "docker": "disconnected", "error": str(e)}


@app.get("/tools")
async def list_tools_rest():
    """REST endpoint to list available tools"""
    return {"tools": get_tools()}


@app.post("/")
async def json_rpc(request: JsonRpcRequest):
    """JSON-RPC 2.0 endpoint for MCP"""
    
    if request.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {"tools": get_tools()}
        }
    
    elif request.method == "tools/call":
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        try:
            result = execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [{"type": "text", "text": result}]
                }
            }
        except ValueError as e:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32601, "message": str(e)}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }
            }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32601, "message": f"Method '{request.method}' not found"}
        }


# ============ REST API (альтернатива MCP) ============

@app.get("/containers")
async def list_containers(all: bool = False):
    """List containers via REST"""
    result = execute_tool("docker_ps", {"all": all})
    return {"containers": json.loads(result)}


@app.get("/containers/{container}/logs")
async def get_logs(container: str, tail: int = 100):
    """Get container logs via REST"""
    result = execute_tool("docker_logs", {"container": container, "tail": tail})
    return {"logs": result}


@app.post("/containers/{container}/start")
async def start_container(container: str):
    """Start container via REST"""
    result = execute_tool("docker_start", {"container": container})
    return {"result": result}


@app.post("/containers/{container}/stop")
async def stop_container(container: str):
    """Stop container via REST"""
    result = execute_tool("docker_stop", {"container": container})
    return {"result": result}


@app.post("/containers/{container}/restart")
async def restart_container(container: str):
    """Restart container via REST"""
    result = execute_tool("docker_restart", {"container": container})
    return {"result": result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8300)
