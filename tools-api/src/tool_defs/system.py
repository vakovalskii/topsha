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
        "description": "Todo list for planning complex tasks.",
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
        "description": "Schedule recurring or delayed tasks. IMPORTANT: 'content' is a TEXT PROMPT (not code!) that will be sent to the agent. Example: content='Найди курс доллара и отправь в ЛС'. The agent will execute this prompt with all its tools.",
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
