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
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CONFIG.proxy_url}/v1/chat/completions",
                json={
                    "model": CONFIG.model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "max_tokens": 8000,
                },
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    return {"error": f"LLM error {resp.status}: {error[:200]}"}
                return await resp.json()
    except Exception as e:
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
        
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except:
                    args = {}
                
                # Execute tool
                tool_result = await execute_tool(name, args, tool_ctx)
                
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
            final_response = msg.get("content", "")
            break
        
        if finish_reason == "stop" and not tool_calls:
            final_response = msg.get("content", "")
            break
    
    # Save to history
    session.history.append({"role": "user", "content": message})
    if final_response:
        session.history.append({"role": "assistant", "content": final_response})
    
    # Trim history
    session.history = trim_history(session.history, CONFIG.max_history * 2, 30000)
    
    final_response = clean_response(final_response)
    agent_logger.info(f"Response: {final_response[:100]}...")
    
    return final_response or "(no response)"
