"""docker_pull and docker_build - Image management"""

import docker

client = docker.from_env()

# ============ DEFINITIONS ============

DEFINITIONS = [
    {
        "name": "docker_pull",
        "description": "Pull an image from registry",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image": {"type": "string", "description": "Image name (e.g. nginx:latest)"}
            },
            "required": ["image"]
        }
    },
    {
        "name": "docker_build",
        "description": "Build an image from Dockerfile",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to build context"},
                "tag": {"type": "string", "description": "Image tag (e.g. myapp:latest)"},
                "dockerfile": {"type": "string", "description": "Dockerfile name"},
                "buildargs": {"type": "object", "description": "Build arguments"},
                "nocache": {"type": "boolean", "description": "No cache", "default": False}
            },
            "required": ["path", "tag"]
        }
    }
]

DEFINITION = DEFINITIONS[0]

# ============ EXECUTORS ============

def docker_pull(image: str) -> str:
    """Pull an image"""
    try:
        img = client.images.pull(image)
        return f"Pulled: {img.tags[0] if img.tags else img.short_id}"
    except docker.errors.APIError as e:
        return f"Error: {str(e)}"


def docker_build(path: str, tag: str, dockerfile: str = None, 
                 buildargs: dict = None, nocache: bool = False) -> str:
    """Build an image"""
    try:
        image, logs = client.images.build(
            path=path,
            tag=tag,
            dockerfile=dockerfile,
            buildargs=buildargs,
            nocache=nocache
        )
        log_output = []
        for log in logs:
            if 'stream' in log:
                log_output.append(log['stream'].strip())
        return f"Built: {tag}\n" + "\n".join(log_output[-20:])
    except docker.errors.BuildError as e:
        return f"Build error: {str(e)}"


EXECUTORS = {
    "docker_pull": docker_pull,
    "docker_build": docker_build
}

def execute(image: str) -> str:
    return docker_pull(image)
