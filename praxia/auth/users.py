"""User model + JSON-on-disk store.

Designed to be a sane default. Production deployments should swap in a real
database via the optional `[enterprise]` extra (planned for Phase 6).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class User:
    id: str
    username: str
    email: str | None
    role: str  # value of Role enum
    api_key_hash: str  # SHA-256 of raw API key
    password_hash: str | None  # bcrypt-style; None when SSO-only
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class UserStore:
    """JSONL on-disk user catalog.

    File layout:
        users.jsonl  — one User per line
        api_keys.jsonl — opaque hash → user_id mapping (write-only audit)
    """

    def __init__(self, storage_dir: Path | str = ".praxia/auth") -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.users_path = self.dir / "users.jsonl"
        self.api_keys_path = self.dir / "api_keys.jsonl"

    # --- User CRUD ---------------------------------------------------------

    def create(
        self,
        *,
        username: str,
        role: str,
        email: str | None = None,
        password: str | None = None,
    ) -> tuple[User, str]:
        """Create a new user. Returns (user, raw_api_key) — store the key safely."""
        if self.get_by_username(username):
            raise ValueError(f"User '{username}' already exists")

        raw_key = secrets.token_urlsafe(32)
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            role=role,
            api_key_hash=_hash(raw_key),
            password_hash=_hash(password) if password else None,
        )
        self._append(user)
        self._record_api_key(user.id, user.api_key_hash)
        return user, raw_key

    def get_by_username(self, username: str) -> User | None:
        for u in self.list_all():
            if u.username == username:
                return u
        return None

    def get_by_id(self, user_id: str) -> User | None:
        for u in self.list_all():
            if u.id == user_id:
                return u
        return None

    def get_by_api_key(self, raw_key: str) -> User | None:
        h = _hash(raw_key)
        for u in self.list_all():
            if u.api_key_hash == h and u.is_active:
                return u
        return None

    def list_all(self) -> list[User]:
        if not self.users_path.exists():
            return []
        out: list[User] = []
        with self.users_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(User(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    def update(self, user: User) -> None:
        users = [u for u in self.list_all() if u.id != user.id]
        users.append(user)
        with self.users_path.open("w", encoding="utf-8") as f:
            for u in users:
                f.write(json.dumps(asdict(u), ensure_ascii=False) + "\n")

    def deactivate(self, user_id: str) -> None:
        u = self.get_by_id(user_id)
        if not u:
            return
        u.is_active = False
        self.update(u)

    def rotate_api_key(self, user_id: str) -> str:
        u = self.get_by_id(user_id)
        if not u:
            raise ValueError(f"Unknown user_id: {user_id}")
        raw = secrets.token_urlsafe(32)
        u.api_key_hash = _hash(raw)
        self.update(u)
        self._record_api_key(user_id, u.api_key_hash)
        return raw

    # --- Internals ---------------------------------------------------------

    def _append(self, user: User) -> None:
        with self.users_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(user), ensure_ascii=False) + "\n")

    def _record_api_key(self, user_id: str, api_key_hash: str) -> None:
        with self.api_keys_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {"user_id": user_id, "hash": api_key_hash, "ts": time.time()},
                    ensure_ascii=False,
                )
                + "\n"
            )


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
