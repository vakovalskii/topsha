"""Bash command execution tool - runs in per-user Docker sandbox"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from config import CONFIG
from security import check_command, sanitize_output
from logger import tool_logger
from models import ToolResult, ToolContext

# Import sandbox
from tools.sandbox import execute_in_sandbox, mark_user_active

# Flag to enable/disable sandbox (set by main.py after init)
SANDBOX_ENABLED = False


def set_sandbox_enabled(enabled: bool):
    """Enable or disable sandbox mode"""
    global SANDBOX_ENABLED
    SANDBOX_ENABLED = enabled
    tool_logger.info(f"Sandbox mode: {'ENABLED' if enabled else 'DISABLED'}")


async def tool_run_command(args: dict, ctx: ToolContext) -> ToolResult:
    """Execute shell command in user's sandbox"""
    command = args.get("command", "")
    
    if not command:
        return ToolResult(False, error="No command provided")
    
    # Security check (admin users bypass some patterns)
    dangerous, blocked, reason = check_command(command, ctx.chat_type, ctx.is_admin)
    if blocked:
        return ToolResult(False, error=f"🚫 BLOCKED: {reason}")
    
    if dangerous:
        return ToolResult(False, error=f"⚠️ Dangerous: {reason}. Approval not implemented.")
    
    user_id = str(ctx.user_id)
    tool_logger.info(f"[{user_id}] Executing: {command[:100]}...")
    
    # Use sandbox if available
    if SANDBOX_ENABLED:
        mark_user_active(user_id)
        success, output, sandboxed = await execute_in_sandbox(user_id, command, ctx.cwd)
        
        if sandboxed:
            output = sanitize_output(output)
            
            # Truncate long output
            if len(output) > CONFIG.max_tool_output:
                head = output[:int(CONFIG.max_tool_output * 0.6)]
                tail = output[-int(CONFIG.max_tool_output * 0.3):]
                output = f"{head}\n\n... [TRIMMED] ...\n\n{tail}"
            
            if success:
                return ToolResult(True, output=output or "(empty output)")
            else:
                return ToolResult(False, error=output)
        
        # Fallback to local if sandbox failed
        tool_logger.warning(f"Sandbox unavailable for {user_id}, using local execution")
    
    # Local execution (fallback or no sandbox)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=ctx.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=CONFIG.command_timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            tool_logger.warning(f"Command timed out: {command[:50]}...")
            return ToolResult(False, error="Command timed out")
        
        output = (stdout or stderr or b"").decode("utf-8", errors="replace")
        output = sanitize_output(output)
        
        # Truncate long output
        if len(output) > CONFIG.max_tool_output:
            head = output[:int(CONFIG.max_tool_output * 0.6)]
            tail = output[-int(CONFIG.max_tool_output * 0.3):]
            output = f"{head}\n\n... [TRIMMED] ...\n\n{tail}"
        
        if proc.returncode != 0:
            tool_logger.warning(f"Command failed (exit {proc.returncode}): {command[:50]}...")
            return ToolResult(False, error=f"Exit {proc.returncode}: {output}")
        
        return ToolResult(True, output=output or "(empty output)")
        
    except Exception as e:
        tool_logger.error(f"Command error: {e}")
        return ToolResult(False, error=str(e))
