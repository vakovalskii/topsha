"""Admin API endpoints for the admin panel"""

import os
import json
import subprocess
import asyncio
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import docker

# For system metrics
import psutil


def _read_model_name() -> str:
    """Read model name from Docker secret or env"""
    paths = ["/run/secrets/model_name", "/run/secrets/model_name.txt"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    value = f.read().strip()
                    if value:
                        return value
            except:
                pass
    return os.getenv("MODEL_NAME", "gpt-4")


router = APIRouter(prefix="/api/admin", tags=["admin"])

# Docker client
docker_client = None
try:
    docker_client = docker.from_env()
except:
    pass


# ============ MODELS ============

class ConfigUpdate(BaseModel):
    agent: Optional[dict] = None
    bot: Optional[dict] = None
    security: Optional[dict] = None
    limits: Optional[dict] = None
    access: Optional[dict] = None


class AccessToggle(BaseModel):
    enabled: bool


class AccessModeUpdate(BaseModel):
    mode: str  # "public", "admin_only", "allowlist"


class AllowlistUpdate(BaseModel):
    user_id: int
    action: str  # "add" or "remove"


class PatternRequest(BaseModel):
    pattern: str


class ToolToggle(BaseModel):
    enabled: bool


# ============ SYSTEM METRICS ============

# Store previous network stats for rate calculation
_prev_net_io = None
_prev_net_time = None


@router.get("/system/metrics")
async def get_system_metrics():
    """Get host system metrics (CPU, Memory, Disk, Network)"""
    global _prev_net_io, _prev_net_time
    
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory
        mem = psutil.virtual_memory()
        
        # Disk - root partition
        disk = psutil.disk_usage('/')
        
        # Network - calculate rate
        net_io = psutil.net_io_counters()
        current_time = time.time()
        
        recv_rate = 0
        sent_rate = 0
        
        if _prev_net_io and _prev_net_time:
            time_delta = current_time - _prev_net_time
            if time_delta > 0:
                recv_rate = (net_io.bytes_recv - _prev_net_io.bytes_recv) / time_delta
                sent_rate = (net_io.bytes_sent - _prev_net_io.bytes_sent) / time_delta
        
        _prev_net_io = net_io
        _prev_net_time = current_time
        
        return {
            "cpu_percent": cpu_percent,
            "cpu_count": psutil.cpu_count(),
            "memory_total": mem.total,
            "memory_used": mem.used,
            "memory_available": mem.available,
            "memory_percent": mem.percent,
            "disk_total": disk.total,
            "disk_used": disk.used,
            "disk_free": disk.free,
            "disk_percent": disk.percent,
            "network_bytes_recv": net_io.bytes_recv,
            "network_bytes_sent": net_io.bytes_sent,
            "network_recv_rate": recv_rate,
            "network_sent_rate": sent_rate,
            "uptime": time.time() - psutil.boot_time(),
            "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get system metrics: {e}")


# ============ STATS ============

@router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    stats = {
        "active_users": 0,
        "active_sandboxes": 0,
        "requests_today": 0,
        "tools_executed": 0,
        "recent_requests": [],
        "security_events": []
    }
    
    # Count sandboxes
    if docker_client:
        containers = docker_client.containers.list(filters={"name": "sandbox_"})
        stats["active_sandboxes"] = len(containers)
    
    # Count workspaces
    workspace = os.getenv("WORKSPACE", "/workspace")
    if os.path.isdir(workspace):
        users = [d for d in os.listdir(workspace) if d.isdigit()]
        stats["active_users"] = len(users)
    
    return stats


@router.get("/health")
async def get_health():
    """Health check for all services"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ============ SERVICES ============

@router.get("/services")
async def get_services():
    """Get list of Docker services (fast, no stats)"""
    if not docker_client:
        return []
    
    services = []
    target_containers = ["core", "bot", "proxy", "userbot", "admin"]
    
    for name in target_containers:
        try:
            c = docker_client.containers.get(name)
            # Fast info only - no stats() call which is very slow
            services.append({
                "name": name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "-",
                "uptime": c.attrs.get("State", {}).get("StartedAt", "")[:19].replace("T", " "),
                "memory": "-",
                "cpu": "-",
                "ports": ", ".join([f"{p}" for p in c.ports.keys()]) if c.ports else ""
            })
        except docker.errors.NotFound:
            services.append({
                "name": name,
                "status": "not found",
                "image": "-",
                "uptime": "-",
                "memory": "-",
                "cpu": "-"
            })
        except Exception as e:
            services.append({
                "name": name,
                "status": "error",
                "image": str(e)[:50],
                "uptime": "-",
                "memory": "-",
                "cpu": "-"
            })
    
    return services


@router.get("/services/{name}/stats")
async def get_service_stats(name: str):
    """Get detailed stats for a single service (slow, calls docker stats)"""
    if not docker_client:
        raise HTTPException(503, "Docker not available")
    
    try:
        c = docker_client.containers.get(name)
        # This is slow (~2s) - only call when needed
        stats = await asyncio.get_event_loop().run_in_executor(
            None, lambda: c.stats(stream=False)
        )
        
        mem_usage = stats.get("memory_stats", {}).get("usage", 0)
        mem_limit = stats.get("memory_stats", {}).get("limit", 1)
        mem_percent = (mem_usage / mem_limit * 100) if mem_limit else 0
        
        cpu_delta = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0) - \
                   stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
        system_delta = stats.get("cpu_stats", {}).get("system_cpu_usage", 0) - \
                      stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
        cpu_percent = (cpu_delta / system_delta * 100) if system_delta else 0
        
        return {
            "name": name,
            "memory": f"{mem_usage // (1024*1024)}MB ({mem_percent:.1f}%)",
            "cpu": f"{cpu_percent:.1f}%",
            "memory_bytes": mem_usage,
            "memory_limit": mem_limit
        }
    except docker.errors.NotFound:
        raise HTTPException(404, f"Service {name} not found")
    
    return services


@router.post("/services/{name}/restart")
async def restart_service(name: str):
    """Restart a service"""
    if not docker_client:
        raise HTTPException(503, "Docker not available")
    try:
        c = docker_client.containers.get(name)
        c.restart(timeout=10)
        return {"success": True}
    except docker.errors.NotFound:
        raise HTTPException(404, f"Service {name} not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/services/{name}/stop")
async def stop_service(name: str):
    """Stop a service"""
    if not docker_client:
        raise HTTPException(503, "Docker not available")
    try:
        c = docker_client.containers.get(name)
        c.stop(timeout=10)
        return {"success": True}
    except docker.errors.NotFound:
        raise HTTPException(404, f"Service {name} not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/services/{name}/start")
async def start_service(name: str):
    """Start a service"""
    if not docker_client:
        raise HTTPException(503, "Docker not available")
    try:
        c = docker_client.containers.get(name)
        c.start()
        return {"success": True}
    except docker.errors.NotFound:
        raise HTTPException(404, f"Service {name} not found")
    except Exception as e:
        raise HTTPException(500, str(e))


# ============ CONFIG ============

CONFIG_FILE = "/workspace/_shared/admin_config.json"


def _default_access_mode() -> str:
    """Map env ACCESS_MODE to core mode (bot uses 'admin', core uses 'admin_only')."""
    mode = os.getenv("ACCESS_MODE", "admin_only")
    return "admin_only" if mode == "admin" else mode


def load_config():
    """Load config from file"""
    default = {
        "agent": {
            "model": _read_model_name(),
            "temperature": 0.7,
            "max_iterations": 30,
            "max_history": 10,
            "tool_timeout": 120
        },
        "bot": {
            "reactions_enabled": True,
            "thoughts_enabled": True,
            "reaction_chance": 0.15,
            "ignore_chance": 0.05,
            "max_length": 4000
        },
        "security": {
            "approval_required": True,
            "block_patterns": True,
            "sandbox_enabled": True,
            "max_blocked": 3
        },
        "limits": {
            "sandbox_ttl": 10,
            "sandbox_memory": "512m",
            "workspace_limit": 500,
            "max_concurrent": 10
        },
        "access": {
            "bot_enabled": True,
            "userbot_enabled": True,
            "mode": _default_access_mode(),
            "admin_id": int(os.getenv("ADMIN_USER_ID", "0")),  # 0 = not set, configure via UI
            "allowlist": []  # list of user_ids
        }
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
                # Deep merge - add new default keys to saved config
                result = {}
                for section, values in default.items():
                    if isinstance(values, dict):
                        result[section] = {**values, **saved.get(section, {})}
                    else:
                        result[section] = saved.get(section, values)
                return result
        except:
            pass
    return default


def save_config(config):
    """Save config to file"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    # Ensure file is writable by all (for container user)
    try:
        os.chmod(CONFIG_FILE, 0o666)
    except:
        pass


@router.get("/config")
async def get_config():
    """Get current configuration"""
    return load_config()


@router.put("/config")
async def update_config(data: ConfigUpdate):
    """Update configuration"""
    config = load_config()
    
    if data.agent:
        config["agent"] = {**config.get("agent", {}), **data.agent}
    if data.bot:
        config["bot"] = {**config.get("bot", {}), **data.bot}
    if data.security:
        config["security"] = {**config.get("security", {}), **data.security}
    if data.limits:
        config["limits"] = {**config.get("limits", {}), **data.limits}
    if data.access:
        config["access"] = {**config.get("access", {}), **data.access}
    
    save_config(config)
    return {"success": True}


# ============ ACCESS CONTROL ============

@router.get("/access")
async def get_access():
    """Get access control status"""
    config = load_config()
    access = config.get("access", {})
    return {
        "bot_enabled": access.get("bot_enabled", True),
        "userbot_enabled": access.get("userbot_enabled", True),
        "mode": access.get("mode", "admin_only"),
        "admin_id": access.get("admin_id", int(os.getenv("ADMIN_USER_ID", "0")))
    }


@router.put("/access/bot")
async def toggle_bot(data: AccessToggle):
    """Enable/disable bot"""
    config = load_config()
    if "access" not in config:
        config["access"] = {}
    config["access"]["bot_enabled"] = data.enabled
    save_config(config)
    return {"success": True, "bot_enabled": data.enabled}


@router.put("/access/userbot")
async def toggle_userbot(data: AccessToggle):
    """Enable/disable userbot"""
    config = load_config()
    if "access" not in config:
        config["access"] = {}
    config["access"]["userbot_enabled"] = data.enabled
    save_config(config)
    return {"success": True, "userbot_enabled": data.enabled}


@router.put("/access/mode")
async def set_access_mode(data: AccessModeUpdate):
    """Set access mode: public, admin_only, or allowlist"""
    if data.mode not in ["public", "admin_only", "allowlist"]:
        raise HTTPException(400, "Invalid mode. Use: public, admin_only, allowlist")
    
    config = load_config()
    if "access" not in config:
        config["access"] = {}
    config["access"]["mode"] = data.mode
    save_config(config)
    return {"success": True, "mode": data.mode}


class AdminIdUpdate(BaseModel):
    admin_id: int


@router.put("/access/admin")
async def set_admin_id(data: AdminIdUpdate):
    """Set admin user ID"""
    if data.admin_id <= 0:
        raise HTTPException(400, "Invalid admin_id. Must be a positive Telegram user ID")
    
    config = load_config()
    if "access" not in config:
        config["access"] = {}
    config["access"]["admin_id"] = data.admin_id
    save_config(config)
    return {"success": True, "admin_id": data.admin_id}


@router.get("/access/allowlist")
async def get_allowlist():
    """Get current allowlist"""
    config = load_config()
    access = config.get("access", {})
    return {
        "allowlist": access.get("allowlist", []),
        "admin_id": access.get("admin_id", int(os.getenv("ADMIN_USER_ID", "0")))
    }


@router.post("/access/allowlist")
async def update_allowlist(data: AllowlistUpdate):
    """Add or remove user from allowlist"""
    config = load_config()
    if "access" not in config:
        config["access"] = {}
    if "allowlist" not in config["access"]:
        config["access"]["allowlist"] = []
    
    allowlist = config["access"]["allowlist"]
    
    if data.action == "add":
        if data.user_id not in allowlist:
            allowlist.append(data.user_id)
    elif data.action == "remove":
        if data.user_id in allowlist:
            allowlist.remove(data.user_id)
    else:
        raise HTTPException(400, "Invalid action. Use: add, remove")
    
    config["access"]["allowlist"] = allowlist
    save_config(config)
    return {"success": True, "allowlist": allowlist}


# ============ SECURITY PATTERNS ============

PATTERNS_FILE = "/app/src/approvals/blocked-patterns.json"

@router.get("/security/patterns")
async def get_security_patterns():
    """Get blocked patterns"""
    patterns = []
    if os.path.exists(PATTERNS_FILE):
        try:
            with open(PATTERNS_FILE) as f:
                patterns = json.load(f)
        except:
            pass
    return {"patterns": patterns}


@router.post("/security/patterns")
async def add_security_pattern(req: PatternRequest):
    """Add a blocked pattern"""
    patterns = []
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE) as f:
            patterns = json.load(f)
    
    if req.pattern not in patterns:
        patterns.append(req.pattern)
        with open(PATTERNS_FILE, "w") as f:
            json.dump(patterns, f, indent=2)
    
    return {"success": True}


@router.delete("/security/patterns")
async def delete_security_pattern(req: PatternRequest):
    """Delete a blocked pattern"""
    patterns = []
    if os.path.exists(PATTERNS_FILE):
        with open(PATTERNS_FILE) as f:
            patterns = json.load(f)
    
    if req.pattern in patterns:
        patterns.remove(req.pattern)
        with open(PATTERNS_FILE, "w") as f:
            json.dump(patterns, f, indent=2)
    
    return {"success": True}


# ============ TOOLS ============

import aiohttp

TOOLS_API_URL = os.getenv("TOOLS_API_URL", "http://tools-api:8100")

@router.get("/tools")
async def get_tools():
    """Get available tools from Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TOOLS_API_URL}/tools",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tools = []
                    for tool in data.get("tools", []):
                        tools.append({
                            "name": tool["name"],
                            "description": tool.get("description", "")[:100],
                            "enabled": tool.get("enabled", True),
                            "icon": "🔧"
                        })
                    return {"tools": tools}
    except Exception as e:
        print(f"Tools API error: {e}")
    
    # Fallback to local
    from tools import TOOL_DEFINITIONS
    tools = []
    for tool in TOOL_DEFINITIONS:
        tools.append({
            "name": tool["function"]["name"],
            "description": tool["function"].get("description", "")[:100],
            "enabled": True,
            "icon": "🔧"
        })
    return {"tools": tools}


@router.put("/tools/{name}")
async def toggle_tool(name: str, data: ToolToggle):
    """Enable/disable a tool via Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{TOOLS_API_URL}/tools/{name}",
                json={"enabled": data.enabled},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, f"Tools API error")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


# ============ USERS & SANDBOXES ============

@router.get("/sandboxes")
async def get_sandboxes():
    """Get active sandboxes"""
    if not docker_client:
        return {"sandboxes": []}
    
    sandboxes = []
    containers = docker_client.containers.list(filters={"name": "sandbox_"})
    
    for c in containers:
        user_id = c.name.replace("sandbox_", "")
        ports = list(c.ports.keys()) if c.ports else []
        
        sandboxes.append({
            "user_id": user_id,
            "container_id": c.id[:12],
            "ports": [p.split("/")[0] for p in ports],
            "active_for": c.attrs.get("State", {}).get("StartedAt", "")[:19].replace("T", " ")
        })
    
    return {"sandboxes": sandboxes}


@router.delete("/sandboxes/{user_id}")
async def kill_sandbox(user_id: str):
    """Kill a user's sandbox"""
    if not docker_client:
        raise HTTPException(503, "Docker not available")
    
    try:
        c = docker_client.containers.get(f"sandbox_{user_id}")
        c.stop(timeout=1)
        c.remove(force=True)
        return {"success": True}
    except docker.errors.NotFound:
        raise HTTPException(404, "Sandbox not found")
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/sessions")
async def get_sessions():
    """Get all user sessions from workspace"""
    workspace = os.getenv("WORKSPACE", "/workspace")
    sessions = []
    
    if not os.path.isdir(workspace):
        return {"sessions": []}
    
    for user_dir in os.listdir(workspace):
        user_path = os.path.join(workspace, user_dir)
        
        # Skip non-numeric directories (like _shared)
        if not user_dir.isdigit() or not os.path.isdir(user_path):
            continue
        
        session_file = os.path.join(user_path, "SESSION.json")
        memory_file = os.path.join(user_path, "MEMORY.md")
        
        # Get session data
        message_count = 0
        last_message = None
        history = []
        
        if os.path.exists(session_file):
            try:
                with open(session_file) as f:
                    data = json.load(f)
                    history = data.get("history", [])
                    message_count = len(history)
                    if history:
                        last_message = history[-1].get("user", "")[:100]
            except:
                pass
        
        # Get last active time from file modification
        last_active = None
        for check_file in [session_file, memory_file]:
            if os.path.exists(check_file):
                mtime = os.path.getmtime(check_file)
                dt = datetime.fromtimestamp(mtime)
                if last_active is None or mtime > last_active:
                    last_active = mtime
                    last_active_str = dt.strftime("%Y-%m-%d %H:%M")
        
        if last_active is None:
            # Fallback to directory mtime
            mtime = os.path.getmtime(user_path)
            last_active_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        
        sessions.append({
            "user_id": user_dir,
            "message_count": message_count,
            "last_active": last_active_str,
            "last_message": last_message
        })
    
    # Sort by last_active descending
    sessions.sort(key=lambda x: x["last_active"], reverse=True)
    
    return {"sessions": sessions}


@router.get("/sessions/{user_id}")
async def get_session_detail(user_id: str):
    """Get detailed session data for a user"""
    workspace = os.getenv("WORKSPACE", "/workspace")
    user_path = os.path.join(workspace, user_id)
    
    if not os.path.isdir(user_path):
        raise HTTPException(404, "User not found")
    
    session_file = os.path.join(user_path, "SESSION.json")
    memory_file = os.path.join(user_path, "MEMORY.md")
    
    result = {
        "user_id": user_id,
        "history": [],
        "memory": ""
    }
    
    if os.path.exists(session_file):
        try:
            with open(session_file) as f:
                data = json.load(f)
                result["history"] = data.get("history", [])
        except:
            pass
    
    if os.path.exists(memory_file):
        try:
            with open(memory_file) as f:
                result["memory"] = f.read()
        except:
            pass
    
    return result


@router.delete("/sessions/{user_id}")
async def clear_session(user_id: str):
    """Clear a user's session history"""
    workspace = os.getenv("WORKSPACE", "/workspace")
    session_file = os.path.join(workspace, user_id, "SESSION.json")
    
    if os.path.exists(session_file):
        try:
            with open(session_file, 'w') as f:
                json.dump({"history": []}, f)
            return {"success": True}
        except Exception as e:
            raise HTTPException(500, str(e))
    
    raise HTTPException(404, "Session not found")


# ============ LOGS ============

@router.get("/logs/{service}")
async def get_logs(service: str, lines: int = 100):
    """Get service logs"""
    if not docker_client:
        return {"logs": ["Docker not available"]}
    
    try:
        c = docker_client.containers.get(service)
        log_bytes = c.logs(tail=lines, timestamps=False)
        log_lines = log_bytes.decode("utf-8", errors="replace").split("\n")
        return {"logs": log_lines}
    except docker.errors.NotFound:
        return {"logs": [f"Service {service} not found"]}
    except Exception as e:
        return {"logs": [f"Error: {e}"]}


# ============ MCP SERVERS ============

class McpServerCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = None


@router.get("/mcp/servers")
async def get_mcp_servers():
    """Get MCP servers from Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TOOLS_API_URL}/mcp/servers",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"MCP API error: {e}")
    return {"servers": []}


@router.post("/mcp/servers")
async def add_mcp_server(data: McpServerCreate):
    """Add MCP server via Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOOLS_API_URL}/mcp/servers",
                json=data.dict(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    raise HTTPException(resp.status, error)
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.delete("/mcp/servers/{name}")
async def remove_mcp_server(name: str):
    """Remove MCP server via Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{TOOLS_API_URL}/mcp/servers/{name}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to remove server")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.post("/mcp/servers/{name}/refresh")
async def refresh_mcp_server(name: str):
    """Refresh tools from MCP server"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOOLS_API_URL}/mcp/servers/{name}/refresh",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to refresh")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.post("/mcp/refresh-all")
async def refresh_all_mcp():
    """Refresh all MCP servers"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOOLS_API_URL}/mcp/refresh-all",
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to refresh")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


# ============ SKILLS ============

class SkillToggle(BaseModel):
    enabled: bool


class SkillInstall(BaseModel):
    name: str
    source: str = "anthropic"


@router.get("/skills")
async def get_skills():
    """Get skills from Tools API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TOOLS_API_URL}/skills",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"Skills API error: {e}")
    return {"skills": []}


@router.get("/skills/available")
async def get_available_skills():
    """Get available skills to install"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{TOOLS_API_URL}/skills/available",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"Skills API error: {e}")
    return {"skills": []}


@router.put("/skills/{name}")
async def toggle_skill(name: str, data: SkillToggle):
    """Enable/disable a skill"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{TOOLS_API_URL}/skills/{name}",
                json={"enabled": data.enabled},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to toggle skill")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.post("/skills/scan")
async def scan_skills():
    """Scan for skills"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOOLS_API_URL}/skills/scan",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to scan")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.post("/skills/install")
async def install_skill(data: SkillInstall):
    """Install a skill from Anthropic or other source"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{TOOLS_API_URL}/skills/install",
                json=data.dict(),
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error = await resp.text()
                    raise HTTPException(resp.status, error)
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


@router.delete("/skills/{name}")
async def uninstall_skill(name: str):
    """Uninstall a skill"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{TOOLS_API_URL}/skills/{name}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to uninstall")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Tools API unavailable: {e}")


# ============ SCHEDULED TASKS ============

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://scheduler:8400")

@router.get("/tasks")
async def get_all_tasks():
    """Get all scheduled tasks from scheduler service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SCHEDULER_URL}/tasks", timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to get tasks")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Scheduler unavailable: {e}")


@router.get("/tasks/user/{user_id}")
async def get_user_tasks(user_id: int):
    """Get tasks for a specific user from scheduler service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SCHEDULER_URL}/tasks?user_id={user_id}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {"tasks": data.get("tasks", []), "user_id": user_id}
                else:
                    raise HTTPException(resp.status, "Failed to get tasks")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Scheduler unavailable: {e}")


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a scheduled task via scheduler service"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{SCHEDULER_URL}/tasks/{task_id}", timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    raise HTTPException(404, "Task not found")
                else:
                    raise HTTPException(resp.status, "Failed to cancel task")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Scheduler unavailable: {e}")


@router.get("/tasks/stats")
async def get_tasks_stats():
    """Get scheduler statistics"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SCHEDULER_URL}/stats", timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    raise HTTPException(resp.status, "Failed to get stats")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Scheduler unavailable: {e}")


@router.post("/tasks/{task_id}/run")
async def run_task_now(task_id: str):
    """Run a task immediately"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{SCHEDULER_URL}/tasks/{task_id}/run", timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    raise HTTPException(404, "Task not found")
                else:
                    raise HTTPException(resp.status, "Failed to run task")
    except aiohttp.ClientError as e:
        raise HTTPException(503, f"Scheduler unavailable: {e}")


# ============ SEARCH CONFIG ============

SEARCH_CONFIG_FILE = "/data/search_config.json"

DEFAULT_SEARCH_CONFIG = {
    "mode": "coding",
    "model": "glm-4.7-flash",
    "count": 10,
    "recency_filter": "noLimit",
    "timeout": 120,
    "response_model": ""
}


class SearchConfigUpdate(BaseModel):
    mode: Optional[str] = None
    model: Optional[str] = None
    count: Optional[int] = None
    recency_filter: Optional[str] = None
    timeout: Optional[int] = None
    response_model: Optional[str] = None


@router.get("/search")
async def get_search_config():
    """Get search configuration"""
    try:
        if os.path.exists(SEARCH_CONFIG_FILE):
            with open(SEARCH_CONFIG_FILE) as f:
                saved = json.load(f)
                return {**DEFAULT_SEARCH_CONFIG, **saved}
    except:
        pass
    return DEFAULT_SEARCH_CONFIG.copy()


@router.put("/search")
async def update_search_config(data: SearchConfigUpdate):
    """Update search configuration
    
    mode: 'coding' (Coding Plan - Chat Completions + tools) or 'legacy' (separate web_search endpoint)
    model: ZAI model for coding mode (e.g. glm-4.7-flash, glm-4.7)
    count: number of search results (1-50)
    recency_filter: oneDay, oneWeek, oneMonth, oneYear, noLimit
    timeout: request timeout in seconds
    """
    try:
        config = DEFAULT_SEARCH_CONFIG.copy()
        if os.path.exists(SEARCH_CONFIG_FILE):
            with open(SEARCH_CONFIG_FILE) as f:
                config = {**config, **json.load(f)}
    except:
        pass
    
    updates = data.model_dump(exclude_none=True)
    # Allow explicitly setting response_model to empty string
    if data.response_model is not None:
        updates["response_model"] = data.response_model
    if "mode" in updates and updates["mode"] not in ("coding", "legacy"):
        raise HTTPException(400, "mode must be 'coding' or 'legacy'")
    if "recency_filter" in updates and updates["recency_filter"] not in ("oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"):
        raise HTTPException(400, "recency_filter must be oneDay, oneWeek, oneMonth, oneYear, or noLimit")
    
    config.update(updates)
    
    os.makedirs(os.path.dirname(SEARCH_CONFIG_FILE), exist_ok=True)
    with open(SEARCH_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    return {"success": True, **config}


# ============ LOCALE (Language) ============

LOCALE_CONFIG_FILE = "/data/bot_locale.json"

SUPPORTED_LANGUAGES = [
    {"code": "ru", "name": "Русский"},
    {"code": "en", "name": "English"},
]


class LocaleUpdate(BaseModel):
    language: str


@router.get("/locale")
async def get_locale():
    """Get current bot language setting"""
    lang = "ru"
    try:
        if os.path.exists(LOCALE_CONFIG_FILE):
            with open(LOCALE_CONFIG_FILE) as f:
                data = json.load(f)
                lang = data.get("language", "ru")
    except:
        pass
    return {"language": lang, "supported": SUPPORTED_LANGUAGES}


@router.put("/locale")
async def update_locale(data: LocaleUpdate):
    """Update bot language"""
    lang = data.language.strip().lower()
    supported_codes = [l["code"] for l in SUPPORTED_LANGUAGES]
    if lang not in supported_codes:
        raise HTTPException(400, f"Unsupported language: {lang}. Supported: {supported_codes}")
    
    os.makedirs(os.path.dirname(LOCALE_CONFIG_FILE), exist_ok=True)
    with open(LOCALE_CONFIG_FILE, "w") as f:
        json.dump({"language": lang}, f)
    
    return {"success": True, "language": lang}


# ============ TIMEZONE ============

TIMEZONE_CONFIG_FILE = "/data/timezone.json"

COMMON_TIMEZONES = [
    "Europe/Moscow", "Europe/Kiev", "Europe/Minsk",
    "Europe/London", "Europe/Berlin", "Europe/Paris",
    "America/New_York", "America/Chicago", "America/Los_Angeles",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Dubai",
    "UTC",
]


@router.get("/timezone")
async def get_timezone():
    """Get current timezone setting"""
    current_tz = os.getenv("TZ", "UTC")
    saved_tz = current_tz
    try:
        if os.path.exists(TIMEZONE_CONFIG_FILE):
            with open(TIMEZONE_CONFIG_FILE) as f:
                data = json.load(f)
                saved_tz = data.get("timezone", current_tz)
    except:
        pass
    
    now = None
    try:
        from datetime import datetime
        import subprocess
        result = subprocess.run(["date", "+%Y-%m-%d %H:%M:%S %Z"], capture_output=True, text=True, timeout=5)
        now = result.stdout.strip() if result.returncode == 0 else None
    except:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "current": current_tz,
        "saved": saved_tz,
        "now": now,
        "common": COMMON_TIMEZONES,
    }


class TimezoneUpdate(BaseModel):
    timezone: str


@router.put("/timezone")
async def update_timezone(data: TimezoneUpdate):
    """Save timezone setting. Requires container restart to take effect."""
    tz = data.timezone.strip()
    if not tz:
        raise HTTPException(400, "Timezone cannot be empty")
    
    os.makedirs(os.path.dirname(TIMEZONE_CONFIG_FILE), exist_ok=True)
    with open(TIMEZONE_CONFIG_FILE, "w") as f:
        json.dump({"timezone": tz}, f)
    
    # Also update current process TZ (takes effect immediately for this container)
    os.environ["TZ"] = tz
    try:
        import time
        time.tzset()
    except:
        pass
    
    return {"success": True, "timezone": tz, "note": "Restart all containers for full effect"}


# ============ ASR CONFIG ============

ASR_CONFIG_FILE = "/data/asr_config.json"

DEFAULT_ASR_CONFIG = {
    "enabled": True,
    "url": "http://host.docker.internal:8080",
    "language": "ru",
    "max_duration": 120,
    "timeout": 60,
}


class ASRConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    url: Optional[str] = None
    language: Optional[str] = None
    max_duration: Optional[int] = None
    timeout: Optional[int] = None


@router.get("/asr")
async def get_asr_config():
    """Get ASR (Speech-to-Text) configuration"""
    try:
        if os.path.exists(ASR_CONFIG_FILE):
            with open(ASR_CONFIG_FILE) as f:
                saved = json.load(f)
                return {**DEFAULT_ASR_CONFIG, **saved}
    except:
        pass
    return DEFAULT_ASR_CONFIG.copy()


@router.put("/asr")
async def update_asr_config(data: ASRConfigUpdate):
    """Update ASR configuration"""
    try:
        config = DEFAULT_ASR_CONFIG.copy()
        if os.path.exists(ASR_CONFIG_FILE):
            with open(ASR_CONFIG_FILE) as f:
                config = {**config, **json.load(f)}
    except:
        pass
    
    updates = data.model_dump(exclude_none=True)
    config.update(updates)
    
    os.makedirs(os.path.dirname(ASR_CONFIG_FILE), exist_ok=True)
    with open(ASR_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    return {"success": True, **config}


@router.get("/asr/health")
async def check_asr_health():
    """Check ASR server health"""
    import aiohttp
    config = DEFAULT_ASR_CONFIG.copy()
    try:
        if os.path.exists(ASR_CONFIG_FILE):
            with open(ASR_CONFIG_FILE) as f:
                config = {**config, **json.load(f)}
    except:
        pass
    
    url = config.get("url", "")
    if not url:
        return {"status": "disabled", "url": ""}
    
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{url}/health/ready") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    data["url"] = url
                    return data
                return {"status": "error", "url": url, "http_status": resp.status}
    except Exception as e:
        return {"status": "error", "url": url, "error": str(e)}


# ============ SYSTEM PROMPT ============

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "src", "agent", "system.txt")


class SystemPromptUpdate(BaseModel):
    content: str


@router.get("/prompt")
async def get_system_prompt():
    """Get current system prompt"""
    try:
        if os.path.exists(SYSTEM_PROMPT_PATH):
            with open(SYSTEM_PROMPT_PATH, "r") as f:
                content = f.read()
            return {
                "content": content,
                "path": SYSTEM_PROMPT_PATH,
                "length": len(content),
                "lines": content.count("\n") + 1
            }
        else:
            return {"content": "", "error": "System prompt file not found"}
    except Exception as e:
        raise HTTPException(500, f"Failed to read prompt: {e}")


@router.put("/prompt")
async def update_system_prompt(data: SystemPromptUpdate):
    """Update system prompt"""
    try:
        # Backup old prompt
        backup_path = SYSTEM_PROMPT_PATH + ".backup"
        if os.path.exists(SYSTEM_PROMPT_PATH):
            with open(SYSTEM_PROMPT_PATH, "r") as f:
                old_content = f.read()
            with open(backup_path, "w") as f:
                f.write(old_content)
        
        # Write new prompt
        with open(SYSTEM_PROMPT_PATH, "w") as f:
            f.write(data.content)
        
        return {
            "success": True,
            "length": len(data.content),
            "lines": data.content.count("\n") + 1,
            "backup": backup_path
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update prompt: {e}")


@router.post("/prompt/restore")
async def restore_system_prompt():
    """Restore system prompt from backup"""
    backup_path = SYSTEM_PROMPT_PATH + ".backup"
    try:
        if not os.path.exists(backup_path):
            raise HTTPException(404, "No backup found")
        
        with open(backup_path, "r") as f:
            content = f.read()
        
        with open(SYSTEM_PROMPT_PATH, "w") as f:
            f.write(content)
        
        return {
            "success": True,
            "restored": True,
            "length": len(content)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to restore: {e}")
