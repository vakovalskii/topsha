"""File Operations Tools

Tools for reading, writing, editing, and searching files.
"""

TOOLS = {
    "read_file": {
        "enabled": True,
        "name": "read_file",
        "description": "Read file contents. Always read before editing.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "offset": {"type": "integer", "description": "Starting line (1-based)"},
                "limit": {"type": "integer", "description": "Number of lines"}
            },
            "required": ["path"]
        }
    },
    
    "write_file": {
        "enabled": True,
        "name": "write_file",
        "description": "Write content to file. Creates if doesn't exist.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    },
    
    "edit_file": {
        "enabled": True,
        "name": "edit_file",
        "description": "Edit file by replacing text. old_text must match exactly.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"},
                "old_text": {"type": "string", "description": "Text to find"},
                "new_text": {"type": "string", "description": "Replacement text"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    
    "delete_file": {
        "enabled": True,
        "name": "delete_file",
        "description": "Delete a file within workspace.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to file"}
            },
            "required": ["path"]
        }
    },
    
    "search_files": {
        "enabled": True,
        "name": "search_files",
        "description": "Search for files by glob pattern.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"}
            },
            "required": ["pattern"]
        }
    },
    
    "search_text": {
        "enabled": True,
        "name": "search_text",
        "description": "Search text in files using grep.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Text/regex to search"},
                "path": {"type": "string", "description": "Directory to search"},
                "ignore_case": {"type": "boolean", "description": "Case insensitive"}
            },
            "required": ["pattern"]
        }
    },
    
    "list_directory": {
        "enabled": True,
        "name": "list_directory",
        "description": "List directory contents.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"}
            },
            "required": []
        }
    }
}
