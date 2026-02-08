"""System & Task Tools

Tools for running commands, memory, and task management.
"""

TOOLS = {
    "run_command": {
        "enabled": True,
        "name": "run_command",
        "description": "Run a shell command. Use for: git, npm, pip, python, system ops.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }
    },
    
    "memory": {
        "enabled": True,
        "name": "memory",
        "description": "Long-term memory. Save/read important info across sessions.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "append", "clear"]},
                "content": {"type": "string", "description": "Text to save (for append)"}
            },
            "required": ["action"]
        }
    },
    
    "manage_tasks": {
        "enabled": True,
        "name": "manage_tasks",
        "description": "INTERNAL todo list for agent's own planning. NOT for user requests! NOT for periodic/scheduled tasks! Use schedule_task for 'every X minutes' requests.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "update", "list", "clear"]},
                "id": {"type": "string", "description": "Task ID"},
                "content": {"type": "string", "description": "Task description"},
                "status": {"type": "string", "enum": ["pending", "done", "cancelled"]}
            },
            "required": ["action"]
        }
    },
    
    "schedule_task": {
        "enabled": True,
        "name": "schedule_task",
        "description": "🔔 PERIODIC TASKS! Use for 'every X minutes', 'check regularly', 'monitor'. Set type='agent' for automated actions (search_web, etc). Content is a NATURAL LANGUAGE prompt that agent will execute.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string", 
                    "enum": ["add", "list", "cancel", "run"], 
                    "description": "add=create, list=show, cancel=remove, run=execute now"
                },
                "type": {
                    "type": "string", 
                    "enum": ["message", "agent"], 
                    "description": "'message'=send text reminder, 'agent'=run agent with prompt (can use tools)"
                },
                "content": {
                    "type": "string", 
                    "description": "TEXT PROMPT for agent (NOT code!). Example: 'Найди новости про X и отправь мне'"
                },
                "delay_minutes": {
                    "type": "integer", 
                    "description": "Minutes before first run (default: 1)"
                },
                "recurring": {
                    "type": "boolean", 
                    "description": "Repeat after execution?"
                },
                "interval_minutes": {
                    "type": "integer", 
                    "description": "Repeat interval in minutes (min: 1)"
                },
                "task_id": {
                    "type": "string", 
                    "description": "Task ID (for cancel/run)"
                }
            },
            "required": ["action"]
        }
    }
}
