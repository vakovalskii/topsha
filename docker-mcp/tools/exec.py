"""docker_exec - Execute command in container"""

import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_exec",
    "description": "Execute a command in a running container",
    "inputSchema": {
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name or ID"},
            "command": {"type": "string", "description": "Command to execute"},
            "workdir": {"type": "string", "description": "Working directory"},
            "user": {"type": "string", "description": "User to run as"}
        },
        "required": ["container", "command"]
    }
}

# ============ EXECUTOR ============
def execute(container: str, command: str, workdir: str = None, user: str = None) -> str:
    """Execute command in container"""
    try:
        c = client.containers.get(container)
        result = c.exec_run(command, workdir=workdir, user=user)
        output = result.output.decode('utf-8', errors='replace')
        return f"Exit code: {result.exit_code}\n{output}"
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"
