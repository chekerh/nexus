"""Security utilities for Nexus-UGC.

Provides encryption, authentication, and audit logging for sensitive data.
"""
import os
import json
import base64
import hashlib
import secrets
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Dict, Any

# Try to use cryptography library if available, otherwise use simple obfuscation
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class SecureStorage:
    """Handles encryption/decryption of sensitive tokens."""

    def __init__(self, key_file: Optional[str] = None):
        self.key_file = key_file or self._get_default_key_file()
        self._lock = threading.Lock()
        self._cipher = None
        self._init_cipher()

    def _get_default_key_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / ".security_key")

    def _init_cipher(self):
        """Initialize encryption cipher."""
        if not CRYPTO_AVAILABLE:
            return

        with self._lock:
            if os.path.exists(self.key_file):
                with open(self.key_file, "rb") as f:
                    key = f.read()
                self._cipher = Fernet(key)
            else:
                # Generate new key
                key = Fernet.generate_key()
                os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
                with open(self.key_file, "wb") as f:
                    f.write(key)
                # Set restrictive permissions (owner read/write only)
                os.chmod(self.key_file, 0o600)
                self._cipher = Fernet(key)

    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        if not data:
            return data
        if not CRYPTO_AVAILABLE or not self._cipher:
            # Fallback: base64 encode with simple obfuscation
            return self._simple_obfuscate(data)
        return self._cipher.encrypt(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        """Decrypt string data."""
        if not data:
            return data
        if not CRYPTO_AVAILABLE or not self._cipher:
            return self._simple_deobfuscate(data)
        try:
            return self._cipher.decrypt(data.encode()).decode()
        except Exception:
            # If decryption fails, might be old format - try deobfuscate
            return self._simple_deobfuscate(data)

    def _simple_obfuscate(self, data: str) -> str:
        """Simple obfuscation when crypto not available."""
        # XOR with a derived key from machine-specific data
        key = self._get_machine_key()
        encoded = base64.b64encode(data.encode()).decode()
        xored = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(encoded))
        return "OBF:" + base64.b64encode(xored.encode()).decode()

    def _simple_deobfuscate(self, data: str) -> str:
        """Reverse simple obfuscation."""
        if data.startswith("OBF:"):
            data = data[4:]
        try:
            key = self._get_machine_key()
            xored = base64.b64decode(data.encode()).decode()
            decoded = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(xored))
            return base64.b64decode(decoded.encode()).decode()
        except Exception:
            return data

    def _get_machine_key(self) -> str:
        """Derive a key from machine-specific data."""
        # Use machine-id or hostname as base
        machine_id = ""
        try:
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id") as f:
                    machine_id = f.read().strip()
            elif os.path.exists("/var/lib/dbus/machine-id"):
                with open("/var/lib/dbus/machine-id") as f:
                    machine_id = f.read().strip()
        except Exception:
            pass
        if not machine_id:
            machine_id = os.uname().nodename
        return hashlib.sha256(machine_id.encode()).hexdigest()[:32]


class AuthManager:
    """Simple authentication manager for local access control."""

    def __init__(self, auth_file: Optional[str] = None):
        self.auth_file = auth_file or self._get_default_auth_file()
        self._lock = threading.Lock()
        self._enabled = False
        self._password_hash = None
        self._session_tokens = set()
        self._load_auth()

    def _get_default_auth_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / ".auth_config")

    def _load_auth(self):
        """Load authentication configuration."""
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, "r") as f:
                    config = json.load(f)
                self._enabled = config.get("enabled", False)
                self._password_hash = config.get("password_hash")
            except Exception:
                pass

    def _save_auth(self):
        """Save authentication configuration."""
        os.makedirs(os.path.dirname(self.auth_file), exist_ok=True)
        with open(self.auth_file, "w") as f:
            json.dump({
                "enabled": self._enabled,
                "password_hash": self._password_hash
            }, f)
        os.chmod(self.auth_file, 0o600)

    def is_enabled(self) -> bool:
        return self._enabled

    def setup_password(self, password: str) -> bool:
        """Set up password protection."""
        if not password or len(password) < 8:
            return False
        self._password_hash = self._hash_password(password)
        self._enabled = True
        self._save_auth()
        return True

    def remove_password(self, password: str) -> bool:
        """Remove password protection after verifying."""
        if self.verify_password(password):
            self._enabled = False
            self._password_hash = None
            self._save_auth()
            return True
        return False

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self._enabled or not self._password_hash:
            return True
        return self._hash_password(password) == self._password_hash

    def _hash_password(self, password: str) -> str:
        """Hash password using PBKDF2."""
        salt = b"nexus_ugc_salt_v1"  # In production, use random salt per password
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
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

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or self._get_default_log_file()
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def _get_default_log_file(self) -> str:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        return str(base_dir / "backend" / "data" / "audit.log")

    def log(self, action: str, details: Dict[str, Any], success: bool = True):
        """Log an action."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "details": details,
            "success": success
        }
        with self._lock:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def get_recent(self, limit: int = 100) -> list:
        """Get recent audit entries."""
        if not os.path.exists(self.log_file):
            return []
        with self._lock:
            with open(self.log_file, "r") as f:
                lines = f.readlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
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


def log_audit(action: str, details: Dict[str, Any], success: bool = True):
    """Log audit entry."""
    audit_logger.log(action, details, success)
