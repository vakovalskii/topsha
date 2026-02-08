"""docker_inspect - Get container details"""

import json
import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_inspect",
    "description": "Get detailed information about a container",
    "inputSchema": {
        "type": "object",
        "properties": {
            "container": {"type": "string", "description": "Container name or ID"}
        },
        "required": ["container"]
    }
}

# ============ EXECUTOR ============
def execute(container: str) -> str:
    """Get container details"""
    try:
        c = client.containers.get(container)
        info = {
            "id": c.id,
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            "created": c.attrs["Created"],
            "ports": c.ports,
            "mounts": [
                {"source": m["Source"], "destination": m["Destination"], "mode": m["Mode"]} 
                for m in c.attrs["Mounts"]
            ],
            "env": c.attrs["Config"]["Env"],
            "network": list(c.attrs["NetworkSettings"]["Networks"].keys()),
            "ip": next(iter(c.attrs["NetworkSettings"]["Networks"].values()), {}).get("IPAddress", "N/A")
        }
        return json.dumps(info, indent=2, ensure_ascii=False)
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"
