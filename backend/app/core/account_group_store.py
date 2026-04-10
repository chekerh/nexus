import json
import os
import threading
import uuid
from datetime import datetime, UTC
from typing import Dict, List, Optional


class AccountGroupStore:
    """Thread-safe JSON-backed store for account groups."""

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

    def list_groups(self) -> List[Dict]:
        with self._lock:
            return self._read_data()

    def get_group(self, group_id: str) -> Optional[Dict]:
        with self._lock:
            data = self._read_data()
            for group in data:
                if group.get("id") == group_id:
                    return group
            return None

    def create_group(self, group: Dict) -> Dict:
        with self._lock:
            data = self._read_data()
            new_group = {
                "id": str(uuid.uuid4()),
                "name": group["name"],
                "description": group.get("description", ""),
                "account_ids": group.get("account_ids", []),
                "created_at": group.get("created_at"),
                "updated_at": group.get("updated_at"),
            }
            data.append(new_group)
            self._write_data(data)
            return new_group

    def update_group(self, group_id: str, updates: Dict) -> Optional[Dict]:
        with self._lock:
            data = self._read_data()
            for i, group in enumerate(data):
                if group.get("id") == group_id:
                    if "name" in updates:
                        group["name"] = updates["name"]
                    if "description" in updates:
                        group["description"] = updates["description"]
                    if "account_ids" in updates:
                        group["account_ids"] = updates["account_ids"]
                    group["updated_at"] = updates.get("updated_at")
                    data[i] = group
                    self._write_data(data)
                    return group
            return None

    def delete_group(self, group_id: str) -> bool:
        with self._lock:
            data = self._read_data()
            new_data = [g for g in data if g.get("id") != group_id]
            if len(new_data) == len(data):
                return False
            self._write_data(new_data)
            return True

    def add_account_to_group(self, group_id: str, account_id: str) -> bool:
        with self._lock:
            data = self._read_data()
            for group in data:
                if group.get("id") == group_id:
                    if account_id not in group.get("account_ids", []):
                        group.setdefault("account_ids", []).append(account_id)
                        group["updated_at"] = datetime.now(UTC).isoformat()
                        self._write_data(data)
                    return True
            return False

    def remove_account_from_group(self, group_id: str, account_id: str) -> bool:
        with self._lock:
            data = self._read_data()
            for group in data:
                if group.get("id") == group_id:
                    if account_id in group.get("account_ids", []):
                        group["account_ids"] = [a for a in group["account_ids"] if a != account_id]
                        group["updated_at"] = datetime.now(UTC).isoformat()
                        self._write_data(data)
                    return True
            return False

    def get_groups_for_account(self, account_id: str) -> List[Dict]:
        with self._lock:
            data = self._read_data()
            return [g for g in data if account_id in g.get("account_ids", [])]
