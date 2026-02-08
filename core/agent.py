"""ReAct Agent implementation"""

import os
import json
import re
import aiohttp
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from config import CONFIG
from logger import agent_logger, log_agent_step
from tools import execute_tool, filter_tools_for_session
from models import ToolContext

# Cache for tool definitions
_tools_cache = None
_tools_cache_time = 0
TOOLS_CACHE_TTL = 60  # seconds


def try_fix_json_args(raw_args: str, tool_name: str) -> Optional[dict]:
    """Try to fix malformed JSON from models like DeepSeek
    
    Common issues:
    - Trailing commas: {"a": 1,}
    - Single quotes: {'a': 1}
    - Unquoted keys: {a: 1}
    - Missing closing brace
    - Newlines in strings
    """
    if not raw_args or not raw_args.strip():
        return {}
    
    original = raw_args
    
    # Try basic fixes
    try:
        # Fix trailing commas before } or ]
        fixed = re.sub(r',\s*([}\]])', r'\1', raw_args)
        
        # Fix single quotes to double quotes (careful with nested)
        if "'" in fixed and '"' not in fixed:
            fixed = fixed.replace("'", '"')
        
        # Try parsing
        return json.loads(fixed)
    except:
        pass
    
    # Try extracting JSON from markdown code block
    try:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_args)
        if match:
            return json.loads(match.group(1))
    except:
        pass
    
    # Try finding first { to last }
    try:
        start = raw_args.find('{')
        end = raw_args.rfind('}')
        if start != -1 and end != -1 and end > start:
            subset = raw_args[start:end+1]
            return json.loads(subset)
    except:
        pass
    
    # For simple tools, try to extract key-value pairs
    try:
        # Pattern: key: value or "key": value
        pairs = re.findall(r'["\']?(\w+)["\']?\s*:\s*["\']([^"\']+)["\']', raw_args)
        if pairs:
            return dict(pairs)
    except:
        pass
    
    agent_logger.warning(f"Could not fix JSON for {tool_name}: {original[:200]}")
    return None


@dataclass
class Session:
    """User session"""
    user_id: int
    chat_id: int
    cwd: str
    history: list
    blocked_count: int = 0
    source: str = "bot"  # 'bot' or 'userbot'


class SessionManager:
    """Manage user sessions"""
    def __init__(self):
        self.sessions: dict[str, Session] = {}
    
    def get_key(self, user_id: int, chat_id: int) -> str:
        return f"{user_id}_{chat_id}"
    
    def get(self, user_id: int, chat_id: int) -> Session:
        key = self.get_key(user_id, chat_id)
        
        if key not in self.sessions:
            cwd = os.path.join(CONFIG.workspace, str(user_id))
            os.makedirs(cwd, exist_ok=True)
            
            self.sessions[key] = Session(
                user_id=user_id,
                chat_id=chat_id,
                cwd=cwd,
                history=[]
            )
            agent_logger.info(f"New session: {key}")
        
        return self.sessions[key]
    
    def clear(self, user_id: int, chat_id: int):
        key = self.get_key(user_id, chat_id)
        if key in self.sessions:
            self.sessions[key].history = []
            self.sessions[key].blocked_count = 0
            agent_logger.info(f"Session cleared: {key}")


sessions = SessionManager()


def load_system_prompt_template() -> str:
    """Load system prompt template from file"""
    prompt_file = Path(__file__).parent / "src" / "agent" / "system.txt"
    if prompt_file.exists():
        return prompt_file.read_text()
    
    # Fallback system prompt
    return """You are a helpful AI assistant with access to a Linux environment.
    
You can:
- Execute shell commands
- Read, write, edit, delete files
- Search the web
- Manage reminders and tasks

Always be helpful and concise. Think step by step when solving complex problems.
"""


def format_system_prompt(
    template: str,
    cwd: str,
    tools_list: str,
    user_ports: str,
    skills_list: str = ""
) -> str:
    """Replace placeholders in system prompt template"""
    from datetime import datetime
    
    prompt = template
    prompt = prompt.replace("{{cwd}}", cwd)
    prompt = prompt.replace("{{date}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    prompt = prompt.replace("{{tools}}", tools_list)
    prompt = prompt.replace("{{userPorts}}", user_ports)
    prompt = prompt.replace("{{skills}}", skills_list)
    
    return prompt


async def load_skill_mentions(user_id: str = None) -> str:
    """Load skill mentions for system prompt (name + description only)
    
    Agent loads full instructions on-demand via read_file when needed.
    Skills are available at /data/skills/{name}/ in the container.
    """
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        url = f"{tools_api_url}/skills/mentions"
        if user_id:
            url += f"?user_id={user_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    mentions = data.get("mentions", "")
                    if mentions:
                        return "\n\n" + mentions
    except Exception as e:
        agent_logger.warning(f"Failed to load skill mentions: {e}")
    
    return ""


def trim_history(history: list, max_msgs: int, max_chars: int) -> list:
    """Keep history within limits"""
    if len(history) > max_msgs:
        history = history[-max_msgs:]
    
    # Estimate size
    total = sum(len(json.dumps(m)) for m in history)
    while total > max_chars and len(history) > 2:
        history.pop(0)
        total = sum(len(json.dumps(m)) for m in history)
    
    return history


def save_session_to_file(session: Session):
    """Save session history to SESSION.json file"""
    try:
        session_file = os.path.join(session.cwd, "SESSION.json")
        
        # Convert history to user/assistant format for display
        display_history = []
        i = 0
        while i < len(session.history):
            entry = {}
            msg = session.history[i]
            
            if msg.get("role") == "user":
                # Add date prefix
                date_str = datetime.now().strftime("[%Y-%m-%d]")
                entry["user"] = f"{date_str} {msg.get('content', '')}"
                
                # Check if next message is assistant
                if i + 1 < len(session.history) and session.history[i + 1].get("role") == "assistant":
                    entry["assistant"] = session.history[i + 1].get("content", "")
                    i += 1
                
                display_history.append(entry)
            i += 1
        
        # Keep only last 10 entries
        display_history = display_history[-10:]
        
        with open(session_file, 'w') as f:
            json.dump({"history": display_history}, f, ensure_ascii=False, indent=2)
        
        agent_logger.debug(f"Saved session to {session_file}")
    except Exception as e:
        agent_logger.error(f"Failed to save session: {e}")


def is_mlx_model() -> bool:
    """Check if using MLX backend (doesn't support tool calling)"""
    model = CONFIG.model.lower() if CONFIG.model else ""
    # MLX models typically have mlx in name or are local models
    return "mlx" in model or model.startswith("local/")


def estimate_context_size(messages: list) -> int:
    """Estimate context size in characters"""
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)


async def call_llm(messages: list, tools: list) -> dict:
    """Call LLM via proxy"""
    if not CONFIG.proxy_url:
        return {"error": "No proxy configured"}
    
    # Check context size - MLX struggles with very large contexts
    context_size = estimate_context_size(messages)
    max_context = int(os.getenv("MAX_CONTEXT_CHARS", "40000"))
    
    if context_size > max_context:
        agent_logger.warning(f"Context too large ({context_size} chars > {max_context}), trimming...")
        # Keep system message and trim history
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        user_msg = messages[-1] if messages and messages[-1].get("role") == "user" else None
        
        if system_msg and user_msg:
            # Keep only system + last few messages + user
            middle = messages[1:-1]
            while estimate_context_size([system_msg] + middle + [user_msg]) > max_context and len(middle) > 2:
                middle.pop(0)
            messages = [system_msg] + middle + [user_msg]
            agent_logger.info(f"Trimmed context to {estimate_context_size(messages)} chars")
    
    # MLX doesn't support tool calling - use prompt-based approach
    use_tools = not is_mlx_model() and tools
    
    request_body = {
        "model": CONFIG.model,
        "messages": messages,
        "max_tokens": 8000,
    }
    
    if use_tools:
        request_body["tools"] = tools
        request_body["tool_choice"] = "auto"
    else:
        # For MLX: inject tool descriptions into system prompt
        if tools and is_mlx_model():
            agent_logger.info("MLX mode: tool calling disabled, using prompt-based approach")
            # Note: MLX users should use simpler tasks or switch to OpenAI-compatible API
    
    # Log raw request (truncate long content)
    agent_logger.debug("=" * 60)
    agent_logger.debug("RAW REQUEST:")
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        
        if role == "system":
            agent_logger.debug(f"  [{i}] system: ({len(content)} chars)")
        elif role == "user":
            agent_logger.debug(f"  [{i}] user: {content[:200]}{'...' if len(content) > 200 else ''}")
        elif role == "assistant":
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    agent_logger.debug(f"  [{i}] assistant tool_call: {fn.get('name')}({fn.get('arguments', '')[:100]})")
            else:
                agent_logger.debug(f"  [{i}] assistant: {content[:200] if content else '(no content)'}{'...' if content and len(content) > 200 else ''}")
        elif role == "tool":
            agent_logger.debug(f"  [{i}] tool[{msg.get('tool_call_id', '?')[:8]}]: {content[:100]}{'...' if len(content) > 100 else ''}")
    agent_logger.debug(f"  tools: {len(tools)} definitions")
    agent_logger.debug("=" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CONFIG.proxy_url}/v1/chat/completions",
                json=request_body,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    agent_logger.error(f"RAW RESPONSE ERROR: {resp.status} - {error[:500]}")
                    return {"error": f"LLM error {resp.status}: {error[:200]}"}
                
                result = await resp.json()
                
                # Log raw response
                agent_logger.debug("RAW RESPONSE:")
                agent_logger.debug(f"  id: {result.get('id', '?')}")
                agent_logger.debug(f"  model: {result.get('model', '?')}")
                
                choices = result.get("choices", [])
                for i, choice in enumerate(choices):
                    msg = choice.get("message", {})
                    finish = choice.get("finish_reason", "?")
                    content = msg.get("content", "")
                    tool_calls = msg.get("tool_calls", [])
                    
                    agent_logger.debug(f"  choice[{i}] finish_reason: {finish}")
                    if content:
                        agent_logger.debug(f"  choice[{i}] content: {content[:300]}{'...' if len(content) > 300 else ''}")
                    if tool_calls:
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            agent_logger.debug(f"  choice[{i}] tool_call: {fn.get('name')}({fn.get('arguments', '')[:150]})")
                
                usage = result.get("usage", {})
                agent_logger.debug(f"  usage: prompt={usage.get('prompt_tokens', '?')}, completion={usage.get('completion_tokens', '?')}, total={usage.get('total_tokens', '?')}")
                agent_logger.debug("=" * 60)
                
                return result
    except Exception as e:
        agent_logger.error(f"RAW RESPONSE EXCEPTION: {e}")
        return {"error": str(e)}


async def get_tool_definitions(source: str = "bot", lazy_loading: bool = True) -> list:
    """Get tool definitions from Tools API + bot-specific tools
    
    Shared tools come from Tools API (can be toggled in admin panel)
    Bot-only tools (send_file, send_dm, etc.) are added locally for 'bot' source
    
    If lazy_loading=True, only loads base tools + search_tools capability.
    Agent can discover and load more tools via search_tools/load_tools.
    """
    global _tools_cache, _tools_cache_time
    import time
    
    now = time.time()
    cache_key = f"{source}_{'lazy' if lazy_loading else 'full'}"
    
    # Check if we have cached tools for this source
    if isinstance(_tools_cache, dict) and cache_key in _tools_cache:
        if (now - _tools_cache_time) < TOOLS_CACHE_TTL:
            return _tools_cache[cache_key]
    
    # Initialize cache as dict if needed
    if not isinstance(_tools_cache, dict):
        _tools_cache = {}
    
    tools_api_url = os.getenv("TOOLS_API_URL", "http://tools-api:8100")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Choose endpoint based on lazy_loading
            endpoint = "/tools/base" if lazy_loading else "/tools/enabled"
            
            async with session.get(
                f"{tools_api_url}{endpoint}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tools = data.get("tools", [])
                    
                    # Add bot-only tools for 'bot' source
                    if source == "bot":
                        tools.extend(get_bot_only_tools())
                    
                    _tools_cache[cache_key] = tools
                    _tools_cache_time = now
                    mode = "base (lazy)" if lazy_loading else "all"
                    agent_logger.debug(f"Loaded {len(tools)} {mode} tools for source={source}")
                    return tools
                else:
                    agent_logger.error(f"Tools API error: {resp.status}")
    except Exception as e:
        agent_logger.error(f"Failed to fetch tools from API: {e}")
    
    # Fallback to local definitions if API fails
    from tools import TOOL_DEFINITIONS
    agent_logger.warning("Using local TOOL_DEFINITIONS as fallback")
    return TOOL_DEFINITIONS


def get_bot_only_tools() -> list:
    """Bot-specific tools that are always available for telegram bot"""
    return [
        {
            "type": "function",
            "function": {
                "name": "send_file",
                "description": "Send a file from workspace to the chat.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to file in workspace"},
                        "caption": {"type": "string", "description": "Optional caption"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_dm",
                "description": "Send a private message to current user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer", "description": "User ID (usually current user)"},
                        "text": {"type": "string", "description": "Message text"}
                    },
                    "required": ["user_id", "text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "manage_message",
                "description": "Edit or delete bot messages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["edit", "delete"]},
                        "message_id": {"type": "integer", "description": "Message ID to edit/delete"},
                        "text": {"type": "string", "description": "New text (for edit)"}
                    },
                    "required": ["action", "message_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": "Ask user a question and wait for their answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Question to ask"},
                        "timeout": {"type": "integer", "description": "Seconds to wait (default 60)"}
                    },
                    "required": ["question"]
                }
            }
        }
    ]


def clean_response(text: str) -> str:
    """Remove LLM artifacts from response"""
    if not text:
        return ""
    # Remove thinking blocks with content
    text = re.sub(r'<thinking>[\s\S]*?</thinking>', '', text, flags=re.IGNORECASE)
    # Remove standalone XML-like tags
    text = re.sub(r'</?(final|response|answer|output|reply|thinking)>', '', text, flags=re.IGNORECASE)
    return text.strip()


async def run_agent(
    user_id: int,
    chat_id: int,
    message: str,
    username: str = "",
    chat_type: str = "private",
    source: str = "bot"
) -> str:
    """Run ReAct agent loop"""
    session = sessions.get(user_id, chat_id)
    session.source = source
    
    agent_logger.info(f"Agent run: user={user_id}, chat={chat_id}, source={source}")
    agent_logger.info(f"Message: {message[:100]}...")
    
    # Get tool definitions FIRST (needed for system prompt)
    use_lazy_loading = os.getenv("LAZY_TOOL_LOADING", "true").lower() == "true"
    tool_definitions = await get_tool_definitions(source, lazy_loading=use_lazy_loading)
    tool_definitions = filter_tools_for_session(tool_definitions, chat_type, source)
    
    # Format tools list for prompt
    tools_list = "\n".join([
        f"- {t['function']['name']}: {t['function'].get('description', '')[:100]}"
        for t in tool_definitions
    ])
    
    # Load skill mentions
    skill_mentions = await load_skill_mentions(str(user_id))
    
    # Get user ports
    user_ports = f"{4010 + (user_id % 1000)}-{4010 + (user_id % 1000) + 9}"
    
    # Build system prompt with placeholders replaced
    system_template = load_system_prompt_template()
    system_prompt = format_system_prompt(
        template=system_template,
        cwd=session.cwd,
        tools_list=tools_list,
        user_ports=user_ports,
        skills_list=skill_mentions
    )
    
    # Add workspace info
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    workspace_info = f"\nUser: @{username} (id={user_id})\nWorkspace: {session.cwd}\nTime: {timestamp}\nSource: {source}"
    
    messages = [{"role": "system", "content": system_prompt + workspace_info}]
    messages.extend(session.history)
    messages.append({"role": "user", "content": message})
    
    # Trim if needed
    messages = [messages[0]] + trim_history(messages[1:], CONFIG.max_context_messages, 50000)
    
    tool_ctx = ToolContext(
        cwd=session.cwd,
        session_id=f"{user_id}_{chat_id}",
        user_id=user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        source=source
    )
    
    final_response = ""
    iteration = 0
    
    # Track dynamically loaded tools for this session
    dynamic_tools = []
    
    agent_logger.info(f"Available tools for {chat_type}/{source}: {len(tool_definitions)} (lazy={use_lazy_loading})")
    
    while iteration < CONFIG.max_iterations:
        iteration += 1
        ctx_chars = sum(len(json.dumps(m)) for m in messages)
        log_agent_step(iteration, CONFIG.max_iterations, len(messages), ctx_chars)
        
        # Call LLM
        result = await call_llm(messages, tool_definitions)
        
        if "error" in result:
            agent_logger.error(f"LLM error: {result['error']}")
            return f"Error: {result['error']}"
        
        choices = result.get("choices", [])
        if not choices:
            return "No response from model"
        
        msg = choices[0].get("message", {})
        finish_reason = choices[0].get("finish_reason")
        
        # Add assistant message to history
        messages.append(msg)
        
        # Check for tool calls
        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content", "") or ""
        
        # If no content and no tool_calls - model didn't finish, continue the loop
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if not content and not tool_calls:
            if reasoning:
                agent_logger.info(f"[iter {iteration}] No content/tool_calls but has reasoning, adding continue prompt")
                # Add a continue message to prompt model to finish
                messages.append({
                    "role": "user",
                    "content": "[system: continue - выдай tool_call или финальный ответ в content]"
                })
                continue  # Don't break, continue the loop
            else:
                agent_logger.warning(f"[iter {iteration}] Empty response from model")
                content = "(no response)"
                break
        
        # Log what we got
        agent_logger.info(f"[iter {iteration}] finish_reason={finish_reason}, tool_calls={len(tool_calls)}, content={len(content) if content else 0} chars")
        if content:
            agent_logger.info(f"[iter {iteration}] CONTENT: {content[:200]}{'...' if len(content) > 200 else ''}")
        
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                
                agent_logger.info(f"[iter {iteration}] TOOL CALL: {name}")
                agent_logger.debug(f"[iter {iteration}] TOOL ARGS RAW: {raw_args}")
                
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as e:
                    agent_logger.warning(f"[iter {iteration}] TOOL ARGS PARSE ERROR: {e}")
                    # Try to fix common JSON issues from DeepSeek/other models
                    args = try_fix_json_args(raw_args, name)
                    if args is None:
                        agent_logger.error(f"[iter {iteration}] Could not fix JSON args for {name}")
                        args = {}
                
                # Execute tool
                tool_result = await execute_tool(name, args, tool_ctx)
                
                agent_logger.info(f"[iter {iteration}] TOOL RESULT: success={tool_result.success}, output={len(tool_result.output or '')} chars, error={tool_result.error or 'none'}")
                
                # Handle dynamic tool loading - MCP tools are called directly, no need to load
                # The execute_tool function handles mcp_* tools automatically
                
                # Track blocked commands
                if not tool_result.success and "BLOCKED" in (tool_result.error or ""):
                    session.blocked_count += 1
                    if session.blocked_count >= CONFIG.max_blocked_commands:
                        agent_logger.warning(f"Too many blocked commands: {session.blocked_count}")
                        return "🚫 Session locked due to repeated security violations. /clear to reset."
                
                # Add tool result
                output = (tool_result.output or "(empty)") if tool_result.success else f"Error: {tool_result.error or 'Unknown error'}"
                
                # Trim long output
                if len(output) > CONFIG.max_tool_output:
                    head = output[:int(CONFIG.max_tool_output * 0.6)]
                    tail = output[-int(CONFIG.max_tool_output * 0.3):]
                    output = f"{head}\n\n... [TRIMMED] ...\n\n{tail}"
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": output
                })
        
        else:
            # No tool calls - this is the final response
            agent_logger.info(f"[iter {iteration}] FINAL RESPONSE (no tool calls)")
            final_response = content
            
            # Debug: if content empty but tokens used, log raw message
            if not content:
                agent_logger.warning(f"[iter {iteration}] Empty content! Raw message: {json.dumps(msg, ensure_ascii=False)[:500]}")
            break
        
        if finish_reason == "stop" and not tool_calls:
            final_response = msg.get("content", "")
            break
    
    # Fallback: if no response but had successful tool calls, generate summary
    # BUT: don't use fallback if last tool result was an error
    if not final_response and iteration > 1:
        # Check if last tool result was an error
        last_tool_result = None
        for m in reversed(messages):
            if m.get("role") == "tool":
                last_tool_result = m.get("content", "")
                break
        
        # If last tool failed, don't fallback - let user see the error context
        if last_tool_result and last_tool_result.startswith("Error:"):
            agent_logger.info(f"[fallback] Skipped - last tool failed: {last_tool_result[:100]}")
            final_response = f"Ошибка: {last_tool_result[7:200]}"  # Show error to user
        else:
            # Look for successful tool results
            tool_outputs = []
            for m in messages:
                if m.get("role") == "tool":
                    content = m.get("content", "")
                    if content and not content.startswith("Error:"):
                        first_line = content.split('\n')[0][:100]
                        if first_line and first_line != "(empty)":
                            tool_outputs.append(first_line)
            
            if tool_outputs:
                final_response = f"Готово! {tool_outputs[-1]}" if len(tool_outputs) == 1 else "✅ Готово"
                agent_logger.info(f"[fallback] Generated response from tool outputs")
    
    # Save to history
    session.history.append({"role": "user", "content": message})
    if final_response:
        session.history.append({"role": "assistant", "content": final_response})
    
    # Trim history
    session.history = trim_history(session.history, CONFIG.max_history * 2, 30000)
    
    # Save to file for admin panel
    save_session_to_file(session)
    
    final_response = clean_response(final_response)
    agent_logger.info(f"Response: {final_response[:100]}...")
    
    return final_response or "(no response)"
