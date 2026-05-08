"""TTL-bounded server-side session store for the Streamlit UI.

`st.session_state` lives in memory and is wiped on every browser reload
(a reload closes the WebSocket → Streamlit drops the session). To
survive reloads we mint an opaque short-lived token, hand it to the
browser as a cookie, and store the actual ``user_id`` / ``org_id`` /
``role`` / ``actor_role`` mapping on disk. The cookie carries no
secrets — the token is unguessable random hex and only resolves
server-side.

Public API:

    from praxia.auth.sessions import SessionStore

    store = SessionStore(memory_dir / "sessions", ttl_seconds=1800)
    token = store.create(user_id="alice", org_id="acme", role="admin")
    payload = store.load(token)        # None if missing / expired
    store.touch(token)                 # extend TTL on activity
    store.delete(token)                # explicit signout
    store.purge_expired()              # housekeeping

The on-disk format is one JSON file per token under
``<storage_dir>/<token>.json``. File names are derived from the token
itself, so leakage of the storage directory exposes valid sessions —
keep the filesystem permissioned the same way you'd protect any
auth/* file.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionRecord:
    """One server-side session row."""

    token: str
    user_id: str
    org_id: str = "default-org"
    role: str = "unknown"
    extra: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0  # absolute unix timestamp; 0 → no expiry

    def is_expired(self, now: float | None = None) -> bool:
        if not self.expires_at:
            return False
        return (now or time.time()) >= self.expires_at


class SessionStore:
    """JSON-backed session store with TTL.

    The store is intentionally simple — one small file per session, no
    locking. Concurrent writes to the *same* token are unlikely (only
    `touch()` rewrites a record, and the same browser usually drives
    sequential reruns). The performance ceiling is the filesystem.
    """

    def __init__(
        self,
        storage_dir: Path | str,
        *,
        ttl_seconds: int = 30 * 60,
    ) -> None:
        self.root = Path(storage_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    # ---- internals -------------------------------------------------------

    @staticmethod
    def _is_safe_token(token: str) -> bool:
        # Tokens we mint are 32 hex chars. Reject anything that doesn't
        # look like our own format so a hostile cookie can't make us
        # touch arbitrary paths.
        return (
            isinstance(token, str)
            and 16 <= len(token) <= 128
            and all(c in "0123456789abcdef" for c in token)
        )

    def _path(self, token: str) -> Path:
        return self.root / f"{token}.json"

    def _read(self, token: str) -> SessionRecord | None:
        if not self._is_safe_token(token):
            return None
        path = self._path(token)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        # Filter to known fields so unrelated keys don't blow up.
        known = {f for f in SessionRecord.__dataclass_fields__}
        return SessionRecord(**{k: v for k, v in data.items() if k in known})

    def _write(self, rec: SessionRecord) -> None:
        self._path(rec.token).write_text(
            json.dumps(asdict(rec), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- public API ------------------------------------------------------

    def create(
        self,
        *,
        user_id: str,
        org_id: str = "default-org",
        role: str = "unknown",
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Mint a new session token and persist it. Returns the token."""
        token = secrets.token_hex(16)  # 32 hex chars
        rec = SessionRecord(
            token=token,
            user_id=user_id,
            org_id=org_id,
            role=role,
            extra=extra or {},
            expires_at=time.time() + self.ttl_seconds if self.ttl_seconds else 0.0,
        )
        self._write(rec)
        return token

    def load(self, token: str) -> SessionRecord | None:
        """Return the session if valid + unexpired, else ``None``.

        Expired sessions are deleted as a side effect.
        """
        rec = self._read(token)
        if rec is None:
            return None
        if rec.is_expired():
            self.delete(token)
            return None
        return rec

    def touch(self, token: str) -> SessionRecord | None:
        """Extend the TTL on activity. Returns the updated record."""
        rec = self.load(token)
        if rec is None:
            return None
        if self.ttl_seconds:
            rec.expires_at = time.time() + self.ttl_seconds
            self._write(rec)
        return rec

    def delete(self, token: str) -> bool:
        """Best-effort delete. Returns ``True`` if a file was removed."""
        if not self._is_safe_token(token):
            return False
        path = self._path(token)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def purge_expired(self) -> int:
        """Delete every expired session. Returns count removed."""
        now = time.time()
        removed = 0
        for f in self.root.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            exp = float(data.get("expires_at") or 0)
            if exp and exp < now:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed


__all__ = ["SessionRecord", "SessionStore"]
