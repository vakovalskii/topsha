"""docker_logs - Get container logs"""

import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_logs",
    "description": "Get container logs",
    "inputSchema": {
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name or ID"},
            "tail": {"type": "integer", "description": "Number of lines from end", "default": 100},
            "since": {"type": "string", "description": "Show logs since timestamp"},
            "timestamps": {"type": "boolean", "description": "Show timestamps", "default": False}
        },
        "required": ["container"]
    }
}

# ============ EXECUTOR ============
def execute(container: str, tail: int = 100, since: str = None, timestamps: bool = False) -> str:
    """Get container logs"""
    try:
        c = client.containers.get(container)
        logs = c.logs(tail=tail, since=since, timestamps=timestamps)
        return logs.decode('utf-8', errors='replace')
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"
