"""docker_images - List images"""

import json
import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_images",
    "description": "List Docker images",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Filter by image name"
            }
        }
    }
}

# ============ EXECUTOR ============
def execute(name: str = None) -> str:
    """List Docker images"""
    images = client.images.list(name=name)
    result = []
    for img in images:
        result.append({
            "id": img.short_id,
            "tags": img.tags,
            "size": f"{img.attrs['Size'] / 1024 / 1024:.1f} MB",
            "created": img.attrs["Created"][:19]
        })
    return json.dumps(result, indent=2, ensure_ascii=False)
