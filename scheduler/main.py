"""
Scheduler Service - Persistent task scheduling for agent
Tasks survive container restarts via JSON file storage
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")

app = FastAPI(title="Scheduler Service", version="1.0")

# ============ Configuration ============

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
TASKS_FILE = DATA_DIR / "scheduled_tasks.json"
CORE_URL = os.getenv("CORE_URL", "http://core:4000")
BOT_URL = os.getenv("BOT_URL", "http://bot:4001")

# ============ Models ============

@dataclass
class Task:
    id: str
    user_id: int
    chat_id: int
    task_type: str  # 'message', 'agent'
    content: str
    execute_at: float  # Unix timestamp
    created_at: float
    recurring: bool = False
    interval_minutes: int = 0
    source: str = "bot"  # 'bot' or 'userbot'
    last_run: Optional[float] = None
    run_count: int = 0
    enabled: bool = True

class TaskCreate(BaseModel):
    user_id: int
    chat_id: int
    task_type: str  # 'message' or 'agent'
    content: str
    delay_minutes: int = 1
    recurring: bool = False
    interval_minutes: int = 60
    source: str = "bot"

class TaskUpdate(BaseModel):
    enabled: Optional[bool] = None
    content: Optional[str] = None
    interval_minutes: Optional[int] = None

# ============ Task Storage ============

class TaskStore:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._load()
    
    def _load(self):
        """Load tasks from file"""
        if TASKS_FILE.exists():
            try:
                data = json.loads(TASKS_FILE.read_text())
                for task_data in data.get("tasks", []):
                    task = Task(**task_data)
                    self.tasks[task.id] = task
                logger.info(f"Loaded {len(self.tasks)} tasks from {TASKS_FILE}")
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")
    
    def _save(self):
        """Save tasks to file"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = {"tasks": [asdict(t) for t in self.tasks.values()]}
            TASKS_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save tasks: {e}")
    
    def add(self, task: Task) -> Task:
        self.tasks[task.id] = task
        self._save()
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    def delete(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            return True
        return False
    
    def update(self, task_id: str, **kwargs) -> Optional[Task]:
        task = self.tasks.get(task_id)
        if task:
            for key, value in kwargs.items():
                if value is not None and hasattr(task, key):
                    setattr(task, key, value)
            self._save()
        return task
    
    def get_user_tasks(self, user_id: int) -> list[Task]:
        return [t for t in self.tasks.values() if t.user_id == user_id]
    
    def get_due_tasks(self) -> list[Task]:
        """Get tasks that are due for execution"""
        now = datetime.now().timestamp()
        return [t for t in self.tasks.values() 
                if t.enabled and t.execute_at <= now]
    
    def all(self) -> list[Task]:
        return list(self.tasks.values())

store = TaskStore()

# Track currently running tasks to prevent duplicate execution
running_tasks: set[str] = set()

# ============ Task Executor ============

async def execute_task(task: Task):
    """Execute a scheduled task"""
    # Skip if already running
    if task.id in running_tasks:
        return
    
    running_tasks.add(task.id)
    logger.info(f"Executing task {task.id}: {task.task_type}")
    
    try:
        if task.task_type == "message":
            # Send reminder message via bot
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": task.chat_id,
                    "text": f"⏰ Напоминание: {task.content}"
                }
                url = f"{BOT_URL}/send" if task.source == "bot" else f"{BOT_URL}/send_userbot"
                async with session.post(url, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        logger.info(f"Task {task.id}: message sent")
                    else:
                        logger.error(f"Task {task.id}: failed to send message: {resp.status}")
        
        elif task.task_type == "agent":
            # Run agent with the task content as direct prompt
            async with aiohttp.ClientSession() as session:
                payload = {
                    "user_id": task.user_id,
                    "chat_id": task.chat_id,
                    "message": task.content,  # Direct prompt, no prefix
                    "username": "scheduler",
                    "source": task.source,
                    "chat_type": "private"
                }
                async with session.post(f"{CORE_URL}/api/chat", json=payload, timeout=120) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        response_text = result.get("response", "")
                        logger.info(f"Task {task.id}: agent executed, response: {response_text[:100]}...")
                        
                        # Send response to user via bot
                        if response_text:
                            send_payload = {
                                "chat_id": task.chat_id,
                                "text": f"📅 Scheduled task:\n\n{response_text}"
                            }
                            url = f"{BOT_URL}/send" if task.source == "bot" else f"{BOT_URL}/send_userbot"
                            async with session.post(url, json=send_payload, timeout=30) as send_resp:
                                if send_resp.status == 200:
                                    logger.info(f"Task {task.id}: response sent to chat")
                                else:
                                    logger.error(f"Task {task.id}: failed to send response: {send_resp.status}")
                    else:
                        logger.error(f"Task {task.id}: agent failed: {resp.status}")
        
        # Update task after execution
        task.last_run = datetime.now().timestamp()
        task.run_count += 1
        
        if task.recurring and task.interval_minutes > 0:
            # Reschedule
            task.execute_at = datetime.now().timestamp() + task.interval_minutes * 60
            store._save()
            logger.info(f"Task {task.id}: rescheduled for {task.interval_minutes} minutes")
        else:
            # One-time task - remove it
            store.delete(task.id)
            logger.info(f"Task {task.id}: completed and removed")
    
    except Exception as e:
        logger.error(f"Task {task.id} execution failed: {e}")
    finally:
        # Always remove from running set when done
        running_tasks.discard(task.id)

async def scheduler_loop():
    """Main scheduler loop - checks for due tasks every 5 seconds"""
    logger.info("Scheduler loop started")
    
    while True:
        try:
            due_tasks = store.get_due_tasks()
            for task in due_tasks:
                asyncio.create_task(execute_task(task))
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
        
        await asyncio.sleep(5)

# ============ API Endpoints ============

@app.on_event("startup")
async def startup():
    asyncio.create_task(scheduler_loop())
    logger.info(f"Scheduler service started, {len(store.tasks)} tasks loaded")

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tasks_count": len(store.tasks),
        "tasks_file": str(TASKS_FILE)
    }

@app.get("/tasks")
async def list_tasks(user_id: Optional[int] = None):
    """List all tasks or tasks for a specific user"""
    if user_id:
        tasks = store.get_user_tasks(user_id)
    else:
        tasks = store.all()
    
    now = datetime.now().timestamp()
    result = []
    for task in tasks:
        time_left = int((task.execute_at - now) / 60)
        result.append({
            "id": task.id,
            "user_id": task.user_id,
            "chat_id": task.chat_id,
            "type": task.task_type,
            "content": task.content,
            "next_run": datetime.fromtimestamp(task.execute_at).strftime("%Y-%m-%d %H:%M:%S"),
            "time_left_minutes": time_left,
            "recurring": task.recurring,
            "interval_minutes": task.interval_minutes,
            "source": task.source,
            "enabled": task.enabled,
            "run_count": task.run_count,
            "last_run": datetime.fromtimestamp(task.last_run).strftime("%Y-%m-%d %H:%M:%S") if task.last_run else None,
            "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S")
        })
    
    result.sort(key=lambda x: x["next_run"])
    return {"tasks": result, "total": len(result)}

@app.post("/tasks")
async def create_task(data: TaskCreate):
    """Create a new scheduled task"""
    # Limit tasks per user
    user_tasks = store.get_user_tasks(data.user_id)
    if len(user_tasks) >= 20:
        raise HTTPException(400, "Maximum 20 tasks per user")
    
    # Minimum interval for recurring tasks
    if data.recurring and data.interval_minutes < 1:
        data.interval_minutes = 1
    
    now = datetime.now().timestamp()
    task_id = f"task_{int(now)}_{os.urandom(3).hex()}"
    
    task = Task(
        id=task_id,
        user_id=data.user_id,
        chat_id=data.chat_id,
        task_type=data.task_type,
        content=data.content,
        execute_at=now + data.delay_minutes * 60,
        created_at=now,
        recurring=data.recurring,
        interval_minutes=data.interval_minutes,
        source=data.source
    )
    
    store.add(task)
    
    execute_time = datetime.fromtimestamp(task.execute_at).strftime("%H:%M")
    recur_info = f" (repeat every {data.interval_minutes}min)" if data.recurring else " (once)"
    
    logger.info(f"Created task {task_id} for user {data.user_id}")
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"✅ Scheduled at {execute_time}{recur_info}",
        "next_run": datetime.fromtimestamp(task.execute_at).strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task"""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    now = datetime.now().timestamp()
    return {
        "id": task.id,
        "user_id": task.user_id,
        "chat_id": task.chat_id,
        "type": task.task_type,
        "content": task.content,
        "next_run": datetime.fromtimestamp(task.execute_at).strftime("%Y-%m-%d %H:%M:%S"),
        "time_left_minutes": int((task.execute_at - now) / 60),
        "recurring": task.recurring,
        "interval_minutes": task.interval_minutes,
        "source": task.source,
        "enabled": task.enabled,
        "run_count": task.run_count
    }

@app.put("/tasks/{task_id}")
async def update_task(task_id: str, data: TaskUpdate):
    """Update a task"""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    updates = {}
    if data.enabled is not None:
        updates["enabled"] = data.enabled
    if data.content is not None:
        updates["content"] = data.content
    if data.interval_minutes is not None:
        updates["interval_minutes"] = max(1, data.interval_minutes)
    
    store.update(task_id, **updates)
    return {"success": True, "task_id": task_id}

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user_id: Optional[int] = None):
    """Delete a task"""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    # If user_id provided, check ownership (unless admin)
    if user_id and task.user_id != user_id:
        raise HTTPException(403, "Cannot delete other user's task")
    
    store.delete(task_id)
    logger.info(f"Deleted task {task_id}")
    return {"success": True, "message": f"Task {task_id} deleted"}

@app.post("/tasks/{task_id}/run")
async def run_task_now(task_id: str):
    """Execute a task immediately"""
    task = store.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    
    asyncio.create_task(execute_task(task))
    return {"success": True, "message": f"Task {task_id} triggered"}

# ============ Stats ============

@app.get("/stats")
async def get_stats():
    """Get scheduler statistics"""
    tasks = store.all()
    now = datetime.now().timestamp()
    
    return {
        "total_tasks": len(tasks),
        "active_tasks": len([t for t in tasks if t.enabled]),
        "recurring_tasks": len([t for t in tasks if t.recurring]),
        "due_soon": len([t for t in tasks if t.execute_at - now < 300]),  # Due in 5 min
        "by_type": {
            "message": len([t for t in tasks if t.task_type == "message"]),
            "agent": len([t for t in tasks if t.task_type == "agent"])
        },
        "by_source": {
            "bot": len([t for t in tasks if t.source == "bot"]),
            "userbot": len([t for t in tasks if t.source == "userbot"])
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8400)
