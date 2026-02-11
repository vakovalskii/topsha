"""Security: blocked patterns and output sanitization"""

import re
import json
from pathlib import Path
from logger import security_logger


def load_blocked_patterns() -> list[dict]:
    """Load blocked command patterns from JSON file"""
    patterns_file = Path(__file__).parent / "src" / "approvals" / "blocked-patterns.json"
    if patterns_file.exists():
        with open(patterns_file) as f:
            data = json.load(f)
            patterns = data.get("patterns", [])
            security_logger.info(f"Loaded {len(patterns)} blocked patterns")
            return patterns
    security_logger.warning("No blocked-patterns.json found")
    return []


BLOCKED_PATTERNS = load_blocked_patterns()


# Dangerous commands patterns
DANGEROUS_PATTERNS = [
    (r"\brm\s+-rf\b", "Recursive delete"),
    (r"\bchmod\s+[0-7]{3,4}", "Permission change"),
    (r"\bchown\b", "Owner change"),
    (r"\bkill\b", "Process kill"),
]


def check_command(command: str, chat_type: str = "private", is_admin: bool = False) -> tuple[bool, bool, str]:
    """
    Check if command is blocked or dangerous.
    
    Args:
        command: Command to check
        chat_type: 'private' or 'group'
        is_admin: If True, patterns with admin_bypass=true are skipped
        
    Returns: (dangerous, blocked, reason)
    """
    for pattern_info in BLOCKED_PATTERNS:
        pattern = pattern_info.get("pattern", "")
        reason = pattern_info.get("reason", "Security violation")
        flags = re.IGNORECASE if pattern_info.get("flags") == "i" else 0
        
        # Skip patterns with admin_bypass=true for admin users
        if is_admin and pattern_info.get("admin_bypass", False):
            continue
        
        try:
            if re.search(pattern, command, flags):
                security_logger.warning(f"BLOCKED: {command[:50]}... ({reason})")
                return False, True, reason
        except re.error:
            continue
    
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            if chat_type != "private":
                security_logger.warning(f"DANGEROUS in group: {command[:50]}...")
                return False, True, f"BLOCKED in groups: {reason}"
            return True, False, reason
    
    return False, False, ""


# Secret patterns to sanitize from output
SECRET_PATTERNS = [
    r"([A-Za-z0-9_]*(?:API[_-]?KEY|APIKEY|TOKEN|SECRET|PASSWORD|PASS|CREDENTIAL|AUTH)[A-Za-z0-9_]*)=([^\s\n]+)",
    r"sk-[A-Za-z0-9]{20,}",
    r"tvly-[A-Za-z0-9-]{20,}",
    r"ghp_[A-Za-z0-9]{36,}",
    r"\d{8,12}:[A-Za-z0-9_-]{35}",  # Telegram bot tokens
    r"Bearer\s+[A-Za-z0-9._-]{20,}",
]


def sanitize_output(output: str) -> str:
    """Remove secrets from command output"""
    sanitized = output
    for pattern in SECRET_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


# Sensitive files that should never be read
SENSITIVE_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "secrets.json", ".secrets",
    "id_rsa", "id_ed25519", ".pem", ".key",
}


def is_sensitive_file(path: str) -> bool:
    """Check if file is sensitive"""
    import os
    basename = os.path.basename(path).lower()
    return basename in SENSITIVE_FILES or ".ssh" in path or "/run/secrets" in path
