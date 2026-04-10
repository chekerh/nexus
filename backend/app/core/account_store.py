import json
import os
import threading
import uuid
from typing import Dict, List, Optional
from .security import encrypt_token, decrypt_token, log_audit

# Fields that should be encrypted
ENCRYPTED_FIELDS = [
    "oauth_refresh_token",
    "instagram_access_token",
    "tiktok_refresh_token",
    "tiktok_access_token",
]


class AccountStore:
    """Thread-safe JSON-backed store for connected social accounts."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            self._write_data([])

    def _read_data(self) -> List[Dict]:
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except Exception:
                return []

    def _write_data(self, data: List[Dict]) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_accounts(self, platform: Optional[str] = None) -> List[Dict]:
        with self._lock:
            data = self._read_data()
            accounts = [a for a in data if not platform or a.get("platform") == platform]
            return [self._decrypt_account_fields(a) for a in accounts]

    def get_account(self, account_id: str) -> Optional[Dict]:
        with self._lock:
            data = self._read_data()
            for account in data:
                if account.get("id") == account_id:
                    return self._decrypt_account_fields(account)
            return None

    def _encrypt_account_fields(self, account: Dict) -> Dict:
        """Encrypt sensitive fields in account data."""
        encrypted = dict(account)
        for field in ENCRYPTED_FIELDS:
            if field in encrypted and encrypted[field]:
                encrypted[field] = encrypt_token(encrypted[field])
        return encrypted

    def _decrypt_account_fields(self, account: Dict) -> Dict:
        """Decrypt sensitive fields in account data."""
        decrypted = dict(account)
        for field in ENCRYPTED_FIELDS:
            if field in decrypted and decrypted[field]:
                decrypted[field] = decrypt_token(decrypted[field])
        return decrypted

    def create_account(self, account: Dict) -> Dict:
        with self._lock:
            data = self._read_data()
            new_account = {
                "id": str(uuid.uuid4()),
                "platform": account["platform"],
                "account_name": account["account_name"],
                "auth_mode": account.get("auth_mode", "manual"),
                "notes": account.get("notes", ""),
                "oauth_refresh_token": account.get("oauth_refresh_token", ""),
                "youtube_privacy_status": account.get("youtube_privacy_status", "private"),
                "instagram_user_id": account.get("instagram_user_id", ""),
                "instagram_access_token": account.get("instagram_access_token", ""),
                "tiktok_open_id": account.get("tiktok_open_id", ""),
                "tiktok_refresh_token": account.get("tiktok_refresh_token", ""),
                "tiktok_access_token": account.get("tiktok_access_token", ""),
                "created_at": account.get("created_at"),
            }
            # Encrypt sensitive fields before storing
            new_account = self._encrypt_account_fields(new_account)
            data.append(new_account)
            self._write_data(data)
            # Log the action (without sensitive data)
            log_audit("account_created", {
                "account_id": new_account["id"],
                "platform": new_account["platform"],
                "account_name": new_account["account_name"]
            })
            return self._decrypt_account_fields(new_account)

    def delete_account(self, account_id: str) -> bool:
        with self._lock:
            data = self._read_data()
            # Find account for audit log before deleting
            account = None
            for a in data:
                if a.get("id") == account_id:
                    account = a
                    break
            if not account:
                return False

            new_data = [a for a in data if a.get("id") != account_id]
            self._write_data(new_data)

            # Log the action
            log_audit("account_deleted", {
                "account_id": account_id,
                "platform": account.get("platform"),
                "account_name": account.get("account_name")
            })
            return True
