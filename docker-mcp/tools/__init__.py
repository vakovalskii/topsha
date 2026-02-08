"""
Docker MCP Tools - модульная структура

Каждый tool в отдельном файле содержит:
- DEFINITION/DEFINITIONS: JSON Schema для MCP
- execute()/EXECUTORS: функции выполнения

Структура файлов:
- ps.py         → docker_ps
- images.py     → docker_images  
- run.py        → docker_run
- lifecycle.py  → docker_stop, docker_start, docker_restart, docker_rm
- logs.py       → docker_logs
- exec.py       → docker_exec
- inspect.py    → docker_inspect
- build.py      → docker_pull, docker_build
- resources.py  → docker_networks, docker_volumes, docker_stats
- compose.py    → docker_compose_up, docker_compose_down
"""

from typing import Dict, Callable, List
import importlib
from pathlib import Path

# Registry of all tools
TOOLS: List[dict] = []
EXECUTORS: Dict[str, Callable] = {}


def load_all_tools():
    """Auto-load all tool modules from this directory"""
    global TOOLS, EXECUTORS
    
    if TOOLS:  # Already loaded
        return
    
    tools_dir = Path(__file__).parent
    
    for file in sorted(tools_dir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        
        module_name = file.stem
        try:
            module = importlib.import_module(f".{module_name}", package="tools")
            
            # Handle modules with multiple tools (DEFINITIONS + EXECUTORS)
            if hasattr(module, "DEFINITIONS") and hasattr(module, "EXECUTORS"):
                for defn in module.DEFINITIONS:
                    TOOLS.append(defn)
                    if defn["name"] in module.EXECUTORS:
                        EXECUTORS[defn["name"]] = module.EXECUTORS[defn["name"]]
            
            # Handle single-tool modules (DEFINITION + execute)
            elif hasattr(module, "DEFINITION") and hasattr(module, "execute"):
                TOOLS.append(module.DEFINITION)
                EXECUTORS[module.DEFINITION["name"]] = module.execute
                
        except Exception as e:
            print(f"[docker-mcp] Failed to load tool {module_name}: {e}")


def get_tools() -> List[dict]:
    """Get all tool definitions"""
    load_all_tools()
    return TOOLS


def get_executor(name: str) -> Callable:
    """Get executor function by tool name"""
    load_all_tools()
    return EXECUTORS.get(name)


def execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with arguments"""
    executor = get_executor(name)
    if not executor:
        raise ValueError(f"Tool '{name}' not found")
    return executor(**arguments)
