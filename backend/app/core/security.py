"""Security utilities for Nexus-UGC.

Provides encryption, authentication, and audit logging for sensitive data.
"""

import base64
import contextlib
import hashlib
import json
import logging
import os
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet


class SecureStorage:
    """Handles encryption/decryption of sensitive tokens."""

    def __init__(self, key_file: str | None = None):
        self.key_file = key_file or self._get_default_key_file()
        self._lock = threading.Lock()
        self._cipher = None
        self._init_cipher()

    def _get_default_key_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / ".security_key")

    def _init_cipher(self):
        """Initialize encryption cipher."""
        with self._lock:
            if os.path.exists(self.key_file):
                with open(self.key_file, "rb") as f:
                    key = f.read()
                self._cipher = Fernet(key)
            else:
                # Generate new key — use os.open with mode to avoid chmod race window
                key = Fernet.generate_key()
                os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
                fd = os.open(self.key_file, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(key)
                self._cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        if not data:
            return data
        if not self._cipher:
            raise RuntimeError("Encryption not initialized")
        return self._cipher.encrypt(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        """Decrypt string data. Returns empty string on failure and logs the error."""
        if not data:
            return data
        if not self._cipher:
            raise RuntimeError("Encryption not initialized")
        try:
            return self._cipher.decrypt(data.encode()).decode()
        except Exception as exc:
            logger.error("Decryption failed: %s", exc)
            return ""


class AuthManager:
    """Simple authentication manager for local access control."""

    def __init__(self, auth_file: str | None = None):
        self.auth_file = auth_file or self._get_default_auth_file()
        self._lock = threading.Lock()
        self._enabled = False
        self._password_hash: str | None = None
        self._password_salt: str | None = None
        self._session_tokens: set[str] = set()
        self._load_auth()

    def _get_default_auth_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / ".auth_config")

    def _load_auth(self):
        """Load authentication configuration."""
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file) as f:
                    config = json.load(f)
                self._enabled = config.get("enabled", False)
                self._password_hash = config.get("password_hash")
                self._password_salt = config.get("password_salt")
            except Exception:
                pass

    def _save_auth(self):
        """Save authentication configuration."""
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        fd = os.open(self.auth_file, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(
                {
                    "enabled": self._enabled,
                    "password_hash": self._password_hash,
                    "password_salt": self._password_salt,
                },
                f,
            )

    def is_enabled(self) -> bool:
        return self._enabled

    def setup_password(self, password: str) -> bool:
        """Set up password protection."""
        if not password or len(password) < 8:
            return False
        salt = secrets.token_hex(16)
        self._password_salt = salt
        self._password_hash = self._hash_password(password, salt)
        self._enabled = True
        self._save_auth()
        return True

    def remove_password(self, password: str) -> bool:
        """Remove password protection after verifying."""
        if self.verify_password(password):
            self._enabled = False
            self._password_hash = None
            self._password_salt = None
            self._save_auth()
            return True
        return False

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self._enabled or not self._password_hash:
            return True
        if self._password_salt:
            computed = self._hash_password(password, self._password_salt)
            if computed == self._password_hash:
                return True
        return self._hash_password(password, "nexus_ugc_salt_v1") == self._password_hash

    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password using PBKDF2 with random salt."""
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return base64.b64encode(key).decode()

    def create_session(self) -> str:
        """Create a session token."""
        token = secrets.token_urlsafe(32)
        self._session_tokens.add(token)
        return token

    def verify_session(self, token: str) -> bool:
        """Verify session token."""
        return token in self._session_tokens

    def revoke_session(self, token: str):
        """Revoke session token."""
        self._session_tokens.discard(token)


class AuditLogger:
    """Audit logging for sensitive operations."""

    def __init__(self, log_file: str | None = None):
        self.log_file = log_file or self._get_default_log_file()
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _get_default_log_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / "audit.log")

    def log(self, action: str, details: dict[str, Any], success: bool = True):
        """Log an action."""
        entry = {"timestamp": datetime.now(UTC).isoformat(), "action": action, "details": details, "success": success}
        with self._lock, open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent(self, limit: int = 100) -> list:
        """Get recent audit entries."""
        if not os.path.exists(self.log_file):
            return []
        with self._lock, open(self.log_file) as f:
            lines = f.readlines()
        entries = []
        for line in lines[-limit:]:
            with contextlib.suppress(Exception):
                entries.append(json.loads(line))
        return entries


# Global instances
secure_storage = SecureStorage()
auth_manager = AuthManager()
audit_logger = AuditLogger()


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    return secure_storage.encrypt(token)


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token."""
    return secure_storage.decrypt(encrypted)


def require_auth() -> bool:
    """Check if authentication is required."""
    return auth_manager.is_enabled()


def verify_auth(password: str) -> bool:
    """Verify authentication."""
    return auth_manager.verify_password(password)


def log_audit(action: str, details: dict[str, Any], success: bool = True):
    """Log audit entry."""
    audit_logger.log(action, details, success)
