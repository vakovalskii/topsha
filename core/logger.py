"""Centralized logging for Core"""

import logging
import sys
import os
from datetime import datetime


# Configure logging level from env
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
if LOG_LEVEL not in ("DEBUG", "INFO", "WARNING", "ERROR"):
    LOG_LEVEL = "INFO"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='[%(name)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Log startup level
print(f"[logger] Log level: {LOG_LEVEL}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with consistent formatting"""
    return logging.getLogger(name)


# Pre-configured loggers
core_logger = get_logger("core")
agent_logger = get_logger("agent")
tool_logger = get_logger("tool")
api_logger = get_logger("api")
scheduler_logger = get_logger("scheduler")
security_logger = get_logger("security")


def log_request(user_id: int, chat_id: int, username: str, source: str, message: str):
    """Log incoming API request"""
    api_logger.info("=" * 60)
    api_logger.info(f"REQUEST: user={user_id}, chat={chat_id}, source={source}")
    api_logger.info(f"  from: @{username}")
    api_logger.info(f"  msg: {message[:100]}...")


def log_response(response: str):
    """Log API response"""
    api_logger.info(f"RESPONSE: {response[:200]}...")
    api_logger.info("=" * 60)


def log_tool_call(name: str, args: dict):
    """Log tool execution"""
    args_str = ", ".join(f"{k}={str(v)[:60]}" for k, v in args.items())
    tool_logger.info(f"{name}({args_str})")


def log_tool_result(success: bool, output: str, error: str = ""):
    """Log tool result"""
    if success:
        tool_logger.info(f"→ {output[:80]}...")
    else:
        tool_logger.warning(f"→ ERROR: {error[:80]}")


def log_agent_step(iteration: int, max_iter: int, msg_count: int, ctx_chars: int):
    """Log agent iteration"""
    agent_logger.info(f"Step {iteration}/{max_iter} (ctx: {msg_count} msgs, ~{ctx_chars//1000}k chars)")


def log_security_event(event_type: str, details: str):
    """Log security events"""
    security_logger.warning(f"[{event_type}] {details}")
