"""docker_run - Run a container"""

import docker

client = docker.from_env()

# ============ DEFINITION ============
DEFINITION = {
    "name": "docker_run",
    "description": "Run a new container from an image",
    "inputSchema": {
        "type": "object",
        "properties": {
            "image": {"type": "string", "description": "Image name (e.g. nginx:latest)"},
            "name": {"type": "string", "description": "Container name"},
            "ports": {"type": "object", "description": "Port mapping, e.g. {'80/tcp': 8080}"},
            "environment": {"type": "object", "description": "Environment variables"},
            "volumes": {"type": "object", "description": "Volume mounts"},
            "detach": {"type": "boolean", "description": "Run in background", "default": True},
            "remove": {"type": "boolean", "description": "Remove when exits", "default": False},
            "network": {"type": "string", "description": "Network to connect to"},
            "command": {"type": "string", "description": "Command to run"}
        },
        "required": ["image"]
    }
}

# ============ EXECUTOR ============
def execute(image: str, name: str = None, ports: dict = None, environment: dict = None,
            volumes: dict = None, detach: bool = True, remove: bool = False,
            network: str = None, command: str = None) -> str:
    """Run a new container"""
    try:
        container = client.containers.run(
            image=image,
            name=name,
            ports=ports,
            environment=environment,
            volumes=volumes,
            detach=detach,
            remove=remove,
            network=network,
            command=command
        )
        if detach:
            return f"Container started: {container.name} ({container.short_id})"
        else:
            return container.decode('utf-8') if isinstance(container, bytes) else str(container)
    except docker.errors.ImageNotFound:
        return f"Error: Image '{image}' not found. Try docker_pull first."
    except docker.errors.APIError as e:
        return f"Error: {str(e)}"
