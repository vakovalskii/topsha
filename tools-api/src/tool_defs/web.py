"""Web & Search Tools

Tools for web search and fetching pages.
"""

TOOLS = {
    "search_web": {
        "enabled": True,
        "name": "search_web",
        "description": "Search the internet for current info, news, docs.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    
    "fetch_page": {
        "enabled": True,
        "name": "fetch_page",
        "description": "Fetch and parse URL content as markdown.",
        "source": "builtin",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"}
            },
            "required": ["url"]
        }
    }
}
