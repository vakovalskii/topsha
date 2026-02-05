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
from tools import TOOL_DEFINITIONS, execute_tool
from models import ToolContext


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


def load_system_prompt() -> str:
    """Load system prompt from file"""
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


async def call_llm(messages: list, tools: list) -> dict:
    """Call LLM via proxy"""
    if not CONFIG.proxy_url:
        return {"error": "No proxy configured"}
    
    request_body = {
        "model": CONFIG.model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": 8000,
    }
    
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
    
    # Build system message
    system_prompt = load_system_prompt()
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
    
    while iteration < CONFIG.max_iterations:
        iteration += 1
        ctx_chars = sum(len(json.dumps(m)) for m in messages)
        log_agent_step(iteration, CONFIG.max_iterations, len(messages), ctx_chars)
        
        # Call LLM
        result = await call_llm(messages, TOOL_DEFINITIONS)
        
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
        
        # Some models put tool calls in reasoning/reasoning_content instead of tool_calls
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        if reasoning and not tool_calls:
            # Try to extract JSON tool call from reasoning
            import re
            json_match = re.search(r'\{[^{}]+\}', reasoning)
            if json_match:
                try:
                    reasoning_json = json.loads(json_match.group())
                    agent_logger.info(f"[iter {iteration}] Found JSON in reasoning: {reasoning_json}")
                    
                    # Check if this looks like a tool call (has known keys)
                    if "cursor" in reasoning_json or "id" in reasoning_json:
                        # This is likely fetch_page for search result
                        result_id = reasoning_json.get("cursor") or reasoning_json.get("id")
                        agent_logger.info(f"[iter {iteration}] Interpreting as fetch_page for result {result_id}")
                        
                        # Create synthetic tool call
                        tool_calls = [{
                            "id": f"reasoning_{iteration}",
                            "type": "function",
                            "function": {
                                "name": "fetch_page",
                                "arguments": json.dumps({"result_id": result_id})
                            }
                        }]
                        msg["tool_calls"] = tool_calls
                    elif any(k in reasoning_json for k in ["command", "path", "query", "url"]):
                        # Determine tool from keys
                        if "command" in reasoning_json:
                            tool_name = "run_command"
                        elif "query" in reasoning_json:
                            tool_name = "search_web"
                        elif "url" in reasoning_json:
                            tool_name = "fetch_page"
                        elif "path" in reasoning_json:
                            tool_name = "read_file"
                        else:
                            tool_name = None
                        
                        if tool_name:
                            agent_logger.info(f"[iter {iteration}] Interpreting as {tool_name}")
                            tool_calls = [{
                                "id": f"reasoning_{iteration}",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(reasoning_json)
                                }
                            }]
                            msg["tool_calls"] = tool_calls
                except json.JSONDecodeError:
                    pass
        
        # If still no content and no tool_calls, check if reasoning indicates intent
        if not content and not tool_calls and reasoning:
            reasoning_lower = reasoning.lower()
            
            # Check if model wants to continue but didn't emit tool call
            intent_patterns = [
                ("let's list", "list_directory", {"path": "."}),
                ("list dir", "list_directory", {"path": "."}),
                ("let's check", "list_directory", {"path": "."}),
                ("let's send", "send_file", None),  # Need to find file path
                ("send the file", "send_file", None),
                ("let's read", "read_file", None),
                ("let's search", "search_web", None),
                ("let's fetch", "fetch_page", None),
            ]
            
            for pattern, tool_name, default_args in intent_patterns:
                if pattern in reasoning_lower:
                    agent_logger.info(f"[iter {iteration}] Detected intent '{pattern}' → {tool_name}")
                    
                    # Try to extract path/query from reasoning
                    args = default_args or {}
                    
                    # Extract file path if mentioned
                    import re
                    path_match = re.search(r'(/workspace/[^\s"\']+\.(?:pptx|pdf|txt|py|json|md|html))', reasoning)
                    if path_match:
                        args["path"] = path_match.group(1)
                    elif tool_name == "send_file":
                        # Try to find any .pptx file mention
                        pptx_match = re.search(r'([A-Za-z0-9_-]+\.pptx)', reasoning)
                        if pptx_match:
                            args["path"] = pptx_match.group(1)
                    
                    if tool_name and (args or tool_name == "list_directory"):
                        tool_calls = [{
                            "id": f"intent_{iteration}",
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(args)
                            }
                        }]
                        msg["tool_calls"] = tool_calls
                        agent_logger.info(f"[iter {iteration}] Created synthetic tool call: {tool_name}({args})")
                    break
            
            # If still nothing, use reasoning as content
            if not tool_calls:
                agent_logger.info(f"[iter {iteration}] Using reasoning as content (no intent detected)")
                content = reasoning
                msg["content"] = content
        
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
                except Exception as e:
                    agent_logger.error(f"[iter {iteration}] TOOL ARGS PARSE ERROR: {e}")
                    args = {}
                
                # Execute tool
                tool_result = await execute_tool(name, args, tool_ctx)
                
                agent_logger.info(f"[iter {iteration}] TOOL RESULT: success={tool_result.success}, output={len(tool_result.output or '')} chars, error={tool_result.error or 'none'}")
                
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
    if not final_response and iteration > 1:
        # Look for successful tool results in messages
        tool_outputs = []
        for m in messages:
            if m.get("role") == "tool":
                content = m.get("content", "")
                if content and not content.startswith("Error:"):
                    # Extract first line or result
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
    
    final_response = clean_response(final_response)
    agent_logger.info(f"Response: {final_response[:100]}...")
    
    return final_response or "(no response)"
