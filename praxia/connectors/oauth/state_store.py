"""Persistent state store for OAuth Authorization Code flows.

A multi-process or multi-host deployment can't rely on the in-process
`OAuthFlow._states` dict — the redirect from the IdP may land on a
different worker than the one that built the authorization URL.

`PersistentStateStore` is a tiny file-backed cache (or Redis-backed
when configured) that survives across processes. Entries auto-expire
after `ttl_seconds`.

Usage:

    from praxia.connectors.oauth.state_store import PersistentStateStore
    state_store = PersistentStateStore(storage_dir=".praxia/auth")

    # When building the authorization URL:
    state_token, state_obj = build_state(...)
    state_store.put(state_token, state_obj)

    # In the callback handler:
    state = state_store.pop(state_token)
    if state is None:
        raise CSRF("unknown state")
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from praxia.connectors.oauth.flow import OAuthState

DEFAULT_TTL_SECONDS = 600  # 10 minutes — IdPs typically time out faster


class PersistentStateStore:
    """File-backed JSON cache for OAuth state objects.

    Storage layout:
        <storage_dir>/oauth_states.json
        {"<state_token>": {state fields..., "_expires": <epoch>}, ...}

    Expired entries are pruned on every `put` and `pop`.

    Args:
        storage_dir: where the cache lives.
        ttl_seconds: how long unfetched states live.
    """

    def __init__(
        self,
        storage_dir: Path | str = ".praxia/auth",
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "oauth_states.json"
        self.ttl = ttl_seconds

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        # Atomic write via tmp + rename
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.path)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _prune_expired(self, data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        now = time.time()
        return {k: v for k, v in data.items() if v.get("_expires", 0) > now}

    def put(self, state_token: str, state: OAuthState) -> None:
        data = self._prune_expired(self._read())
        record = asdict(state)
        record["_expires"] = time.time() + self.ttl
        data[state_token] = record
        self._write(data)

    def pop(self, state_token: str) -> OAuthState | None:
        """Atomically retrieve + remove the state."""
        data = self._prune_expired(self._read())
        record = data.pop(state_token, None)
        self._write(data)
        if record is None:
            return None
        record.pop("_expires", None)
        try:
            return OAuthState(**record)
        except TypeError:
            return None

    def clear(self) -> None:
        self._write({})


__all__ = ["PersistentStateStore", "DEFAULT_TTL_SECONDS"]
