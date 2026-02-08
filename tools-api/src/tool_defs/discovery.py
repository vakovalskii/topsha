"""Tool Discovery & Skills

Tools for discovering and loading additional tools dynamically.
"""

TOOLS = {
    "search_tools": {
        "enabled": True,
        "name": "search_tools",
        "description": "🔍 DISCOVER MORE TOOLS! Search available tools by keyword. Use when you need capabilities not in your base toolkit (e.g. 'docker', 'telegram', 'presentation', 'web').",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword (e.g. 'docker', 'telegram', 'file')"},
                "source": {"type": "string", "enum": ["all", "builtin", "mcp"], "description": "Filter by source"},
                "limit": {"type": "integer", "description": "Max results (default: 10)"}
            },
            "required": ["query"]
        }
    },
    
    "load_tools": {
        "enabled": True,
        "name": "load_tools",
        "description": "Load additional tools into your session after finding them with search_tools. Tools will be available immediately.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}, "description": "List of tool names to load"}
            },
            "required": ["names"]
        }
    },
    
    "install_skill": {
        "enabled": True,
        "name": "install_skill",
        "description": "Install a skill from Anthropic's skills repository. Skills add capabilities like creating presentations, documents, etc.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (e.g. 'pptx', 'docx', 'xlsx')"},
                "source": {"type": "string", "enum": ["anthropic", "url"], "description": "Source: 'anthropic' for official skills, 'url' for custom"}
            },
            "required": ["name"]
        }
    },
    
    "list_skills": {
        "enabled": True,
        "name": "list_skills",
        "description": "List available and installed skills.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "installed_only": {"type": "boolean", "description": "Show only installed skills"}
            },
            "required": []
        }
    }
}
