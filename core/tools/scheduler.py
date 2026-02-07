"""Task scheduler - client for scheduler service"""

import sys
import os as os_module
sys.path.insert(0, os_module.path.dirname(os_module.path.dirname(os_module.path.abspath(__file__))))

import os
import aiohttp
from logger import scheduler_logger
from models import ToolResult, ToolContext

# Scheduler service URL
SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://scheduler:8400")


async def _call_scheduler(method: str, path: str, json_data: dict = None) -> tuple[bool, dict]:
    """Make HTTP request to scheduler service"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{SCHEDULER_URL}{path}"
            
            if method == "GET":
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return True, await resp.json()
                    else:
                        text = await resp.text()
                        return False, {"error": text}
            
            elif method == "POST":
                async with session.post(url, json=json_data, timeout=10) as resp:
                    if resp.status == 200:
                        return True, await resp.json()
                    else:
                        text = await resp.text()
                        return False, {"error": text}
            
            elif method == "DELETE":
                async with session.delete(url, timeout=10) as resp:
                    if resp.status == 200:
                        return True, await resp.json()
                    else:
                        text = await resp.text()
                        return False, {"error": text}
        
        return False, {"error": "Unknown method"}
    
    except aiohttp.ClientError as e:
        scheduler_logger.error(f"Scheduler connection error: {e}")
        return False, {"error": f"Scheduler unavailable: {e}"}
    except Exception as e:
        scheduler_logger.error(f"Scheduler error: {e}")
        return False, {"error": str(e)}


async def tool_schedule_task(args: dict, ctx: ToolContext) -> ToolResult:
    """Schedule tasks via scheduler service"""
    action = args.get("action", "list")
    
    if action == "add":
        task_type = args.get("type")
        content = args.get("content")
        if not task_type or not content:
            return ToolResult(False, error="Need type and content")
        
        if task_type not in ["message", "agent"]:
            return ToolResult(False, error="Type must be 'message' or 'agent'")
        
        payload = {
            "user_id": ctx.user_id,
            "chat_id": ctx.chat_id,
            "task_type": task_type,
            "content": content,
            "delay_minutes": args.get("delay_minutes", 1),
            "recurring": args.get("recurring", False),
            "interval_minutes": args.get("interval_minutes", 60),
            "source": ctx.source
        }
        
        ok, data = await _call_scheduler("POST", "/tasks", payload)
        if ok:
            return ToolResult(True, output=data.get("message", "Task created"))
        else:
            return ToolResult(False, error=data.get("error", "Failed to create task"))
    
    elif action == "list":
        ok, data = await _call_scheduler("GET", f"/tasks?user_id={ctx.user_id}")
        if ok:
            tasks = data.get("tasks", [])
            if not tasks:
                return ToolResult(True, output="No scheduled tasks")
            
            lines = []
            for t in tasks:
                recur = f" 🔄 every {t['interval_minutes']}min" if t['recurring'] else ""
                icon = "👤" if t['source'] == "userbot" else "🤖"
                enabled = "✅" if t['enabled'] else "⏸️"
                lines.append(
                    f"• {t['id']}: {icon}{enabled} [{t['type']}] in {t['time_left_minutes']}min{recur}\n"
                    f"  \"{t['content'][:50]}\" (runs: {t['run_count']})"
                )
            
            return ToolResult(True, output=f"Scheduled tasks ({len(tasks)}):\n" + "\n".join(lines))
        else:
            return ToolResult(False, error=data.get("error", "Failed to list tasks"))
    
    elif action == "cancel":
        task_id = args.get("task_id")
        if not task_id:
            return ToolResult(False, error="Need task_id")
        
        ok, data = await _call_scheduler("DELETE", f"/tasks/{task_id}?user_id={ctx.user_id}")
        if ok:
            return ToolResult(True, output=data.get("message", f"Task {task_id} cancelled"))
        else:
            return ToolResult(False, error=data.get("error", "Failed to cancel task"))
    
    elif action == "run":
        task_id = args.get("task_id")
        if not task_id:
            return ToolResult(False, error="Need task_id")
        
        ok, data = await _call_scheduler("POST", f"/tasks/{task_id}/run")
        if ok:
            return ToolResult(True, output=data.get("message", f"Task {task_id} triggered"))
        else:
            return ToolResult(False, error=data.get("error", "Failed to run task"))
    
    return ToolResult(False, error=f"Unknown action: {action}. Use: add, list, cancel, run")


# Keep backward compatibility - dummy Scheduler class
class Scheduler:
    """Deprecated: Use scheduler service instead"""
    def __init__(self):
        self.tasks = {}
        self.user_tasks = {}
    
    def set_callbacks(self, **kwargs):
        pass
    
    async def start(self):
        scheduler_logger.info("Legacy scheduler disabled - using scheduler service")


scheduler = Scheduler()
