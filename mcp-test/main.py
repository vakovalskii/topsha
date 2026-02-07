"""MCP-compatible HTTP server for testing (JSON-RPC 2.0)"""
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, List, Any
import random
from datetime import datetime

app = FastAPI(title="MCP Test Server")

# Simulated tools
TOOLS = [
    {
        "name": "echo",
        "description": "Echo back the input message",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to echo"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "time",
        "description": "Get current server time",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "random",
        "description": "Generate a random number",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min": {"type": "integer", "default": 0},
                "max": {"type": "integer", "default": 100}
            }
        }
    }
]

def execute_tool(name: str, arguments: dict) -> Any:
    """Execute a tool and return result"""
    if name == "echo":
        return {"content": [{"type": "text", "text": arguments.get("message", "")}]}
    elif name == "time":
        return {"content": [{"type": "text", "text": datetime.now().isoformat()}]}
    elif name == "random":
        min_val = arguments.get("min", 0)
        max_val = arguments.get("max", 100)
        return {"content": [{"type": "text", "text": str(random.randint(min_val, max_val))}]}
    else:
        return {"error": f"Unknown tool: {name}"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/tools")
async def list_tools():
    """REST-style tools listing (fallback)"""
    return {"tools": TOOLS}

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Any = 1
    method: str
    params: dict = {}

@app.post("/")
async def jsonrpc_handler(request: JsonRpcRequest):
    """JSON-RPC 2.0 handler for MCP protocol"""
    if request.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {"tools": TOOLS}
        }
    elif request.method == "tools/call":
        name = request.params.get("name", "")
        arguments = request.params.get("arguments", {})
        result = execute_tool(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": result
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32601, "message": f"Method not found: {request.method}"}
        }

class ToolCall(BaseModel):
    name: str
    arguments: dict = {}

@app.post("/tools/call")
async def call_tool(call: ToolCall):
    """REST-style tool call (fallback)"""
    return execute_tool(call.name, call.arguments)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
