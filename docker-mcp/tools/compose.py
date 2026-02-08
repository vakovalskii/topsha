"""docker_compose_up and docker_compose_down"""

import subprocess

# ============ DEFINITIONS ============

DEFINITIONS = [
    {
        "name": "docker_compose_up",
        "description": "Run docker compose up in a directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to directory with docker-compose.yml"},
                "services": {"type": "array", "items": {"type": "string"}, "description": "Services to start"},
                "build": {"type": "boolean", "description": "Build images first", "default": False},
                "detach": {"type": "boolean", "description": "Run in background", "default": True}
            },
            "required": ["path"]
        }
    },
    {
        "name": "docker_compose_down",
        "description": "Run docker compose down in a directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to directory with docker-compose.yml"},
                "volumes": {"type": "boolean", "description": "Remove volumes", "default": False},
                "rmi": {"type": "string", "description": "Remove images: 'all' or 'local'"}
            },
            "required": ["path"]
        }
    }
]

DEFINITION = DEFINITIONS[0]

# ============ EXECUTORS ============

def docker_compose_up(path: str, services: list = None, build: bool = False, detach: bool = True) -> str:
    """Run docker compose up"""
    cmd = ["docker", "compose", "-f", f"{path}/docker-compose.yml", "up"]
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")
    if services:
        cmd.extend(services)
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    return output if output else "Compose up completed"


def docker_compose_down(path: str, volumes: bool = False, rmi: str = None) -> str:
    """Run docker compose down"""
    cmd = ["docker", "compose", "-f", f"{path}/docker-compose.yml", "down"]
    if volumes:
        cmd.append("-v")
    if rmi:
        cmd.extend(["--rmi", rmi])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    output = result.stdout + result.stderr
    return output if output else "Compose down completed"


EXECUTORS = {
    "docker_compose_up": docker_compose_up,
    "docker_compose_down": docker_compose_down
}

def execute(path: str, services: list = None, build: bool = False, detach: bool = True) -> str:
    return docker_compose_up(path, services, build, detach)
