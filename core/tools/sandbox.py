"""Docker Sandbox - isolated container per user

Features:
- One container per active user
- Workspace mounted (only user's own)
- Ports forwarded (user's range 5000-5999)
- No access to secrets or other users
- Auto-cleanup after inactivity (10 min)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import docker
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from logger import tool_logger

# Configuration
SANDBOX_IMAGE = "python:3.11-slim"
CONTAINER_PREFIX = "sandbox_"
# WORKSPACE_HOST_PATH is the host path to mount into sandbox containers
WORKSPACE_HOST = os.getenv("WORKSPACE_HOST_PATH", "/home/ubuntu/LocalTopSH/workspace")
WORKSPACE_LIMIT_MB = 500
COMMAND_TIMEOUT = 120  # seconds
USER_INACTIVITY_TTL = 10  # minutes
CLEANUP_INTERVAL = 5  # minutes


@dataclass
class UserContainer:
    container_id: str
    user_id: str
    ports: list[int]
    last_active: float
    created: float


# Docker client
docker_client: Optional[docker.DockerClient] = None

# Track active user containers
user_containers: dict[str, UserContainer] = {}

# Track used port ranges
used_port_ranges: set[int] = set()


def get_docker_client() -> Optional[docker.DockerClient]:
    """Get or create Docker client"""
    global docker_client
    if docker_client is None:
        try:
            docker_client = docker.from_env()
            docker_client.ping()
            tool_logger.info("Docker client connected")
        except Exception as e:
            tool_logger.warning(f"Docker not available: {e}")
            return None
    return docker_client


def get_user_ports(user_id: str) -> tuple[int, list[int]]:
    """Calculate port range for user (5000-5999, 100 slots of 10 ports)"""
    hash_val = int(user_id[-8:]) % 100 if user_id.isdigit() else hash(user_id) % 100
    base_port = 5000 + (hash_val * 10)
    port_range = list(range(base_port, base_port + 10))
    return base_port, port_range


def find_free_port_range() -> Optional[tuple[int, list[int]]]:
    """Find free port range (fallback if collision)"""
    for slot in range(100):
        base_port = 5000 + (slot * 10)
        if base_port not in used_port_ranges:
            port_range = list(range(base_port, base_port + 10))
            return base_port, port_range
    return None


async def get_or_create_container(user_id: str) -> Optional[UserContainer]:
    """Get or create sandbox container for user"""
    client = get_docker_client()
    if not client:
        return None
    
    # Check existing container
    existing = user_containers.get(user_id)
    if existing:
        try:
            container = client.containers.get(existing.container_id)
            if container.status == "running":
                existing.last_active = datetime.now().timestamp()
                return existing
            # Not running - free ports
            used_port_ranges.discard(existing.ports[0])
        except docker.errors.NotFound:
            if existing.ports:
                used_port_ranges.discard(existing.ports[0])
        user_containers.pop(user_id, None)
    
    # Get port range
    base_port, ports = get_user_ports(user_id)
    
    # Check for collision
    if base_port in used_port_ranges:
        free_range = find_free_port_range()
        if not free_range:
            tool_logger.error("No free port ranges available")
            return None
        base_port, ports = free_range
        tool_logger.info(f"Port collision for {user_id}, using fallback {base_port}-{base_port+9}")
    
    container_name = f"{CONTAINER_PREFIX}{user_id}"
    
    # Remove old container if exists
    try:
        old = client.containers.get(container_name)
        old.stop(timeout=1)
        old.remove(force=True)
    except docker.errors.NotFound:
        pass
    except Exception as e:
        tool_logger.warning(f"Failed to remove old container: {e}")
    
    # Mark ports as used
    used_port_ranges.add(base_port)
    
    tool_logger.info(f"Creating sandbox for user {user_id}, ports {base_port}-{base_port+9}")
    
    # Port bindings
    port_bindings = {f"{p}/tcp": p for p in ports}
    
    try:
        container = client.containers.run(
            SANDBOX_IMAGE,
            command="sleep infinity",
            name=container_name,
            detach=True,
            working_dir=f"/workspace/{user_id}",
            environment={
                "USER_ID": user_id,
                "PORT_BASE": str(base_port),
                "PORTS": ",".join(map(str, ports)),
            },
            volumes={
                f"{WORKSPACE_HOST}/{user_id}": {
                    "bind": f"/workspace/{user_id}",
                    "mode": "rw"
                },
                # Skills directory (read-only for on-demand loading)
                f"{WORKSPACE_HOST}/_shared/skills": {
                    "bind": "/data/skills",
                    "mode": "ro"
                }
            },
            ports=port_bindings,
            mem_limit="512m",
            memswap_limit="512m",
            cpu_period=100000,
            cpu_quota=50000,  # 50% CPU
            pids_limit=100,
            network_mode="topsha_agent-net",  # Same network as other services
            security_opt=["no-new-privileges"],
        )
        
        # Install common tools
        await _exec_raw(container, "apt-get update && apt-get install -y --no-install-recommends curl git jq && rm -rf /var/lib/apt/lists/*")
        
        user_container = UserContainer(
            container_id=container.id,
            user_id=user_id,
            ports=ports,
            last_active=datetime.now().timestamp(),
            created=datetime.now().timestamp(),
        )
        
        user_containers[user_id] = user_container
        tool_logger.info(f"Sandbox {container.short_id} ready for user {user_id}")
        
        return user_container
        
    except Exception as e:
        used_port_ranges.discard(base_port)
        tool_logger.error(f"Failed to create sandbox: {e}")
        return None


async def _exec_raw(container, cmd: str) -> tuple[int, str]:
    """Execute command in container (raw)"""
    try:
        exit_code, output = container.exec_run(
            ["sh", "-c", cmd],
            workdir="/workspace",
        )
        return exit_code, output.decode("utf-8", errors="replace")
    except Exception as e:
        return 1, str(e)


async def execute_in_sandbox(
    user_id: str,
    command: str,
    cwd: Optional[str] = None
) -> tuple[bool, str, bool]:
    """
    Execute command in user's sandbox.
    Returns: (success, output, sandboxed)
    """
    client = get_docker_client()
    if not client:
        return False, "Docker not available - running without sandbox", False
    
    try:
        user_container = await get_or_create_container(user_id)
        if not user_container:
            return False, "Failed to create sandbox container", False
        
        container = client.containers.get(user_container.container_id)
        work_dir = cwd or f"/workspace/{user_id}"
        
        # Intercept df command
        actual_command = command
        if command.strip().startswith("df"):
            actual_command = f'echo "Workspace: $(du -sh /workspace/{user_id} 2>/dev/null | cut -f1) / {WORKSPACE_LIMIT_MB}MB limit"'
        
        # Execute with timeout
        try:
            exit_code, output = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: container.exec_run(
                        ["sh", "-c", actual_command],
                        workdir=work_dir,
                    )
                ),
                timeout=COMMAND_TIMEOUT
            )
            
            output_str = output.decode("utf-8", errors="replace").strip()
            
            # Check workspace size
            warning = await check_workspace_size(user_id)
            if warning:
                output_str = output_str + "\n\n" + warning
            
            # Limit output
            if len(output_str) > 50000:
                output_str = output_str[:50000] + "\n...(truncated)"
            
            return exit_code == 0, output_str or "(no output)", True
            
        except asyncio.TimeoutError:
            return False, f"Timeout: command exceeded {COMMAND_TIMEOUT}s", True
            
    except Exception as e:
        tool_logger.error(f"Sandbox error for {user_id}: {e}")
        return False, f"Sandbox error: {e}", False


async def check_workspace_size(user_id: str) -> Optional[str]:
    """Check workspace size and return warning if exceeded"""
    client = get_docker_client()
    if not client:
        return None
    
    user_container = user_containers.get(user_id)
    if not user_container:
        return None
    
    try:
        container = client.containers.get(user_container.container_id)
        exit_code, output = container.exec_run(
            ["sh", "-c", f"du -sm /workspace/{user_id} 2>/dev/null | cut -f1"],
        )
        size_mb = int(output.decode().strip()) if exit_code == 0 else 0
        
        if size_mb > WORKSPACE_LIMIT_MB:
            return f"⚠️ Workspace: {size_mb}MB / {WORKSPACE_LIMIT_MB}MB (limit exceeded!)"
    except:
        pass
    
    return None


def mark_user_active(user_id: str):
    """Mark user as active"""
    container = user_containers.get(user_id)
    if container:
        container.last_active = datetime.now().timestamp()


async def stop_user_container(user_id: str):
    """Stop and remove user's container"""
    container_info = user_containers.pop(user_id, None)
    if not container_info:
        return
    
    client = get_docker_client()
    if not client:
        return
    
    try:
        container = client.containers.get(container_info.container_id)
        container.stop(timeout=5)
        container.remove(force=True)
        tool_logger.info(f"Removed sandbox for user {user_id}")
    except Exception as e:
        tool_logger.warning(f"Failed to remove sandbox for {user_id}: {e}")
    
    # Free ports
    if container_info.ports:
        used_port_ranges.discard(container_info.ports[0])


async def cleanup_inactive_containers():
    """Cleanup inactive user containers"""
    now = datetime.now().timestamp()
    ttl_seconds = USER_INACTIVITY_TTL * 60
    
    for user_id, container in list(user_containers.items()):
        inactive = now - container.last_active
        
        if inactive > ttl_seconds:
            tool_logger.info(f"User {user_id} inactive for {int(inactive/60)}min, removing sandbox...")
            await stop_user_container(user_id)


async def cleanup_orphan_containers():
    """Cleanup orphan containers from previous runs"""
    client = get_docker_client()
    if not client:
        return
    
    try:
        containers = client.containers.list(all=True)
        orphans = [c for c in containers if c.name.startswith(CONTAINER_PREFIX)]
        
        if orphans:
            tool_logger.info(f"Found {len(orphans)} orphan sandboxes, cleaning up...")
            for c in orphans:
                try:
                    c.stop(timeout=1)
                    c.remove(force=True)
                except:
                    pass
            tool_logger.info("Orphan sandboxes cleaned")
    except Exception as e:
        tool_logger.warning(f"Failed to cleanup orphans: {e}")


async def ensure_sandbox_image():
    """Pull sandbox image if needed"""
    client = get_docker_client()
    if not client:
        return
    
    try:
        client.images.get(SANDBOX_IMAGE)
        tool_logger.info(f"Sandbox image {SANDBOX_IMAGE} ready")
    except docker.errors.ImageNotFound:
        tool_logger.info(f"Pulling sandbox image {SANDBOX_IMAGE}...")
        client.images.pull(SANDBOX_IMAGE)
        tool_logger.info(f"Sandbox image {SANDBOX_IMAGE} pulled")


def get_sandbox_stats() -> dict:
    """Get sandbox statistics"""
    now = datetime.now().timestamp()
    return {
        "active_containers": len(user_containers),
        "containers": [
            {
                "user_id": c.user_id,
                "container_id": c.container_id[:12],
                "ports": f"{c.ports[0]}-{c.ports[-1]}",
                "age_min": int((now - c.created) / 60),
                "inactive_min": int((now - c.last_active) / 60),
            }
            for c in user_containers.values()
        ]
    }


async def sandbox_cleanup_loop():
    """Background task for periodic cleanup"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL * 60)
        await cleanup_inactive_containers()


async def start_sandbox_manager():
    """Start sandbox manager"""
    client = get_docker_client()
    if not client:
        tool_logger.warning("Docker not available! Running without sandbox.")
        return False
    
    await ensure_sandbox_image()
    await cleanup_orphan_containers()
    
    # Start cleanup task
    asyncio.create_task(sandbox_cleanup_loop())
    
    tool_logger.info(f"Sandbox manager started (cleanup every {CLEANUP_INTERVAL}min, TTL {USER_INACTIVITY_TTL}min)")
    return True


async def shutdown_sandbox():
    """Shutdown - remove all containers"""
    tool_logger.info("Shutting down sandbox manager...")
    for user_id in list(user_containers.keys()):
        await stop_user_container(user_id)
