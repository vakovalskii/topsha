"""docker_ps - List containers"""

import json
import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_ps",
    "description": "List running containers. Use all=true to include stopped containers.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "all": {
                "type": "boolean",
                "description": "Include stopped containers",
                "default": False
            },
            "filters": {
                "type": "object",
                "description": "Filters as dict, e.g. {'name': 'myapp'}"
            }
        }
    }
}

# ============ EXECUTOR ============
def execute(all: bool = False, filters: dict = None) -> str:
    """List Docker containers"""
    containers = client.containers.list(all=all, filters=filters)
    result = []
    for c in containers:
        result.append({
            "id": c.short_id,
            "name": c.name,
            "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            "status": c.status,
            "ports": c.ports,
            "created": c.attrs["Created"][:19]
        })
    return json.dumps(result, indent=2, ensure_ascii=False)
