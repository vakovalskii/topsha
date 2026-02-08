"""docker_networks, docker_volumes, docker_stats - Resource management"""

import json
import docker

client = docker.from_env()

# ============ DEFINITIONS ============

DEFINITIONS = [
    {
        "name": "docker_networks",
        "description": "List Docker networks",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "docker_volumes",
        "description": "List Docker volumes",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "docker_stats",
        "description": "Get container resource usage statistics",
        "inputSchema": {
            "type": "object",
            "properties": {
                "container": {"type": "string", "description": "Container name/ID (optional)"}
            }
        }
    }
]

DEFINITION = DEFINITIONS[0]

# ============ EXECUTORS ============

def docker_networks() -> str:
    """List networks"""
    networks = client.networks.list()
    result = []
    for net in networks:
        result.append({
            "id": net.short_id,
            "name": net.name,
            "driver": net.attrs["Driver"],
            "scope": net.attrs["Scope"]
        })
    return json.dumps(result, indent=2, ensure_ascii=False)


def docker_volumes() -> str:
    """List volumes"""
    volumes = client.volumes.list()
    result = []
    for vol in volumes:
        result.append({
            "name": vol.name,
            "driver": vol.attrs["Driver"],
            "mountpoint": vol.attrs["Mountpoint"]
        })
    return json.dumps(result, indent=2, ensure_ascii=False)


def docker_stats(container: str = None) -> str:
    """Get container stats"""
    try:
        if container:
            containers = [client.containers.get(container)]
        else:
            containers = client.containers.list()
        
        result = []
        for c in containers:
            stats = c.stats(stream=False)
            
            # CPU %
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0
            
            # Memory
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            mem_percent = (mem_usage / mem_limit) * 100
            
            result.append({
                "name": c.name,
                "cpu": f"{cpu_percent:.2f}%",
                "memory": f"{mem_usage / 1024 / 1024:.1f}MB / {mem_limit / 1024 / 1024:.1f}MB ({mem_percent:.1f}%)"
            })
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    except docker.errors.NotFound:
        return f"Error: Container '{container}' not found"


EXECUTORS = {
    "docker_networks": docker_networks,
    "docker_volumes": docker_volumes,
    "docker_stats": docker_stats
}

def execute() -> str:
    return docker_networks()
