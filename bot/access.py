"""Access Control - DM Policy like OpenClaw

Modes:
- admin: Only admin can use
- allowlist: Admin + configured users
- public: Anyone can use (with rate limiting)
- pairing: Unknown users get pairing code (OpenClaw-style)
"""

import os
import json
import time
import random
import string
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("bot.access")

# Access mode from env (fallback)
ACCESS_MODE = os.getenv("ACCESS_MODE", "admin")  # admin, allowlist, public, pairing
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Allowlist from env (comma-separated)
_allowed_env = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = set(int(x.strip()) for x in _allowed_env.split(",") if x.strip().isdigit())
ALLOWED_USERS.add(ADMIN_USER_ID)  # Admin always allowed

# Shared config file (written by admin UI via core)
CONFIG_FILE = Path("/data/admin_config.json") if os.path.exists("/data") else Path(__file__).parent / "admin_config.json"

# Pairing storage
PAIRING_FILE = Path("/data/pairing.json") if os.path.exists("/data") else Path(__file__).parent / "pairing.json"
PAIRING_TTL = 300  # 5 minutes for pairing code


def _load_access_config() -> dict:
    """Load access config from shared config file (written by admin UI)"""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            return data.get("access", {})
        except Exception as e:
            logger.error(f"Failed to load config from {CONFIG_FILE}: {e}")
    return {}


@dataclass
class AccessResult:
    allowed: bool
    reason: str
    pairing_code: Optional[str] = None
    is_admin: bool = False


class AccessControl:
    """Manage user access"""
    
    def __init__(self):
        self.mode = ACCESS_MODE
        self.admin_id = ADMIN_USER_ID
        self.allowlist = ALLOWED_USERS.copy()
        self.pairing_codes: dict[str, tuple[int, float]] = {}  # code -> (user_id, timestamp)
        self.approved_users: set[int] = set()
        self._load_approved()
        logger.info(f"Access mode: {self.mode}, admin: {self.admin_id}, allowlist: {len(self.allowlist)} users")
    
    def _load_approved(self):
        """Load approved users from file"""
        if PAIRING_FILE.exists():
            try:
                data = json.loads(PAIRING_FILE.read_text())
                self.approved_users = set(data.get("approved", []))
                logger.info(f"Loaded {len(self.approved_users)} approved users")
            except Exception as e:
                logger.error(f"Failed to load approved users: {e}")
    
    def _save_approved(self):
        """Save approved users to file"""
        try:
            PAIRING_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"approved": list(self.approved_users)}
            PAIRING_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save approved users: {e}")
    
    def _reload_from_config(self):
        """Reload admin_id, mode, and allowlist from shared config file"""
        access = _load_access_config()
        if access:
            new_admin_id = access.get("admin_id")
            if new_admin_id and isinstance(new_admin_id, int) and new_admin_id > 0:
                if new_admin_id != self.admin_id:
                    logger.info(f"Admin ID updated from config: {self.admin_id} -> {new_admin_id}")
                    self.admin_id = new_admin_id

            # Map core mode names to bot mode names (admin_only -> admin)
            new_mode = access.get("mode")
            if new_mode:
                if new_mode == "admin_only":
                    new_mode = "admin"
                if new_mode != self.mode:
                    logger.info(f"Access mode updated from config: {self.mode} -> {new_mode}")
                    self.mode = new_mode

            new_allowlist = access.get("allowlist")
            if isinstance(new_allowlist, list):
                self.allowlist = set(new_allowlist)
                self.allowlist.add(self.admin_id)

    def check_access(self, user_id: int, chat_type: str = "private") -> AccessResult:
        """Check if user has access

        Returns AccessResult with:
        - allowed: True if user can proceed
        - reason: Human-readable reason
        - pairing_code: Code for pairing mode (if applicable)
        - is_admin: True if user is admin
        """
        # Reload config from file (admin UI may have changed it)
        self._reload_from_config()

        is_admin = user_id == self.admin_id

        # Admin always has access
        if is_admin:
            return AccessResult(allowed=True, reason="admin", is_admin=True)

        # Mode: admin only
        if self.mode == "admin":
            return AccessResult(
                allowed=False,
                reason="🔒 Bot is in admin-only mode"
            )
        
        # Mode: allowlist
        if self.mode == "allowlist":
            if user_id in self.allowlist:
                return AccessResult(allowed=True, reason="allowlist")
            return AccessResult(
                allowed=False,
                reason="🚫 You're not in the allowlist. Contact admin."
            )
        
        # Mode: pairing (OpenClaw-style)
        if self.mode == "pairing":
            # Check if already approved
            if user_id in self.approved_users:
                return AccessResult(allowed=True, reason="approved")
            
            # Generate pairing code
            code = self._generate_pairing_code(user_id)
            return AccessResult(
                allowed=False,
                reason=f"🔐 Pairing required!\n\nYour code: <code>{code}</code>\n\n"
                       f"Send this to admin for approval.\n"
                       f"Code expires in {PAIRING_TTL // 60} minutes.",
                pairing_code=code
            )
        
        # Mode: public
        if self.mode == "public":
            return AccessResult(allowed=True, reason="public")
        
        # Unknown mode - deny
        return AccessResult(allowed=False, reason="Unknown access mode")
    
    def _generate_pairing_code(self, user_id: int) -> str:
        """Generate pairing code for user"""
        # Check existing code
        for code, (uid, ts) in list(self.pairing_codes.items()):
            if uid == user_id:
                if time.time() - ts < PAIRING_TTL:
                    return code
                del self.pairing_codes[code]
        
        # Generate new code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        self.pairing_codes[code] = (user_id, time.time())
        
        # Cleanup old codes
        self._cleanup_codes()
        
        return code
    
    def _cleanup_codes(self):
        """Remove expired pairing codes"""
        now = time.time()
        expired = [c for c, (_, ts) in self.pairing_codes.items() if now - ts > PAIRING_TTL]
        for code in expired:
            del self.pairing_codes[code]
    
    def approve_user(self, code: str, approver_id: int) -> tuple[bool, str]:
        """Approve user by pairing code (admin only)
        
        Returns (success, message)
        """
        if approver_id != self.admin_id:
            return False, "Only admin can approve users"
        
        code = code.upper().strip()
        
        if code not in self.pairing_codes:
            return False, f"Code '{code}' not found or expired"
        
        user_id, ts = self.pairing_codes[code]
        
        if time.time() - ts > PAIRING_TTL:
            del self.pairing_codes[code]
            return False, "Code expired"
        
        # Approve user
        self.approved_users.add(user_id)
        del self.pairing_codes[code]
        self._save_approved()
        
        logger.info(f"User {user_id} approved by {approver_id}")
        return True, f"✅ User {user_id} approved!"
    
    def revoke_user(self, user_id: int, revoker_id: int) -> tuple[bool, str]:
        """Revoke user access (admin only)"""
        if revoker_id != self.admin_id:
            return False, "Only admin can revoke access"
        
        if user_id == self.admin_id:
            return False, "Cannot revoke admin"
        
        if user_id in self.approved_users:
            self.approved_users.discard(user_id)
            self._save_approved()
            logger.info(f"User {user_id} revoked by {revoker_id}")
            return True, f"✅ User {user_id} revoked"
        
        if user_id in self.allowlist:
            self.allowlist.discard(user_id)
            return True, f"✅ User {user_id} removed from allowlist"
        
        return False, f"User {user_id} not found in approved/allowlist"
    
    def add_to_allowlist(self, user_id: int, adder_id: int) -> tuple[bool, str]:
        """Add user to allowlist (admin only)"""
        if adder_id != self.admin_id:
            return False, "Only admin can add users"
        
        self.allowlist.add(user_id)
        logger.info(f"User {user_id} added to allowlist by {adder_id}")
        return True, f"✅ User {user_id} added to allowlist"
    
    def get_status(self) -> dict:
        """Get access control status"""
        return {
            "mode": self.mode,
            "admin_id": self.admin_id,
            "allowlist_count": len(self.allowlist),
            "approved_count": len(self.approved_users),
            "pending_codes": len(self.pairing_codes),
            "allowlist": list(self.allowlist),
            "approved": list(self.approved_users),
        }
    
    def set_mode(self, mode: str, setter_id: int) -> tuple[bool, str]:
        """Change access mode (admin only)"""
        if setter_id != self.admin_id:
            return False, "Only admin can change mode"
        
        valid_modes = ["admin", "allowlist", "public", "pairing"]
        if mode not in valid_modes:
            return False, f"Invalid mode. Use: {', '.join(valid_modes)}"
        
        old_mode = self.mode
        self.mode = mode
        logger.info(f"Access mode changed: {old_mode} -> {mode} by {setter_id}")
        return True, f"✅ Mode changed: {old_mode} → {mode}"


# Global instance
access_control = AccessControl()


def check_user_access(user_id: int, chat_type: str = "private") -> AccessResult:
    """Convenience function to check access"""
    return access_control.check_access(user_id, chat_type)
