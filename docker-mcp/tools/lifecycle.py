"""Container lifecycle tools: stop, start, restart, rm"""

import docker

client = docker.from_env()

# ============ DEFINITIONS ============

DEFINITIONS = [
    {
        "name": "docker_stop",
        "description": "Stop a running container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string", "description": "Container name or ID"},
                "timeout": {"type": "integer", "description": "Seconds to wait", "default": 10}
            },
            "required": ["container"]
        }
    },
    {
        "name": "docker_start",
        "description": "Start a stopped container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string", "description": "Container name or ID"}
            },
            "required": ["container"]
        }
    },
    {
        "name": "docker_restart",
        "description": "Restart a container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string", "description": "Container name or ID"},
                "timeout": {"type": "integer", "description": "Seconds to wait", "default": 10}
            },
            "required": ["container"]
        }
    },
    {
        "name": "docker_rm",
        "description": "Remove a container",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string", "description": "Container name or ID"},
                "force": {"type": "boolean", "description": "Force removal", "default": False},
                "v": {"type": "boolean", "description": "Remove volumes", "default": False}
            },
            "required": ["container"]
        }
    }
]

# For single-tool modules compatibility
DEFINITION = DEFINITIONS[0]

# ============ EXECUTORS ============

def docker_stop(container: str, timeout: int = 10) -> str:
    try:
        c = client.containers.get(container)
        c.stop(timeout=timeout)
        return f"Container '{container}' stopped"
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"


def docker_start(container: str) -> str:
    try:
        c = client.containers.get(container)
        c.start()
        return f"Container '{container}' started"
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"


def docker_restart(container: str, timeout: int = 10) -> str:
    try:
        c = client.containers.get(container)
        c.restart(timeout=timeout)
        return f"Container '{container}' restarted"
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"


def docker_rm(container: str, force: bool = False, v: bool = False) -> str:
    try:
        c = client.containers.get(container)
        c.remove(force=force, v=v)
        return f"Container '{container}' removed"
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"


# Map tool names to executors
EXECUTORS = {
    "docker_stop": docker_stop,
    "docker_start": docker_start,
    "docker_restart": docker_restart,
    "docker_rm": docker_rm
}

# Default execute for single-tool compatibility
def execute(container: str, timeout: int = 10) -> str:
    return docker_stop(container, timeout)
