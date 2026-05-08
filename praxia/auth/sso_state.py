"""Short-lived disk-backed store for SSO PKCE state.

`OIDCProvider._pkce_store` is a per-instance dict — fine inside a long-
running FastAPI server, broken in Streamlit because every full page
reload re-imports modules and creates a new provider instance, so the
``state -> verifier`` mapping minted before redirecting to the IdP
disappears by the time the IdP callback hits us back.

This module spills the (state, verifier, redirect_uri, provider_name,
issued_at) tuple to ``.praxia/sso_pending/<state>.json`` with a 10-minute
TTL so `exchange_code()` can rehydrate the verifier no matter which
process runs the callback.

Public API:

    from praxia.auth.sso_state import SSOPendingStore

    store = SSOPendingStore(memory_dir / "sso_pending")
    store.put(state, verifier, redirect_uri, provider_name)
    rec = store.consume(state)   # one-shot read; deletes the file
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class SSOPendingRecord:
    state: str
    verifier: str
    redirect_uri: str
    provider_name: str
    issued_at: float = field(default_factory=time.time)


class SSOPendingStore:
    """JSON-backed store with a built-in TTL on read."""

    def __init__(self, storage_dir: Path | str, *, ttl_seconds: int = 10 * 60) -> None:
        self.root = Path(storage_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _is_safe_state(state: str) -> bool:
        return (
            isinstance(state, str)
            and 16 <= len(state) <= 256
            and all(c.isalnum() or c in "-_" for c in state)
        )

    def _path(self, state: str) -> Path:
        return self.root / f"{state}.json"

    def put(
        self,
        state: str,
        verifier: str,
        redirect_uri: str,
        provider_name: str,
    ) -> None:
        if not self._is_safe_state(state):
            return
        rec = SSOPendingRecord(
            state=state,
            verifier=verifier,
            redirect_uri=redirect_uri,
            provider_name=provider_name,
        )
        self._path(state).write_text(
            json.dumps(asdict(rec), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def consume(self, state: str) -> SSOPendingRecord | None:
        """Read + delete in one shot. Returns ``None`` if state is unknown,
        expired, or malformed."""
        if not self._is_safe_state(state):
            return None
        p = self._path(state)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            try:
                p.unlink()
            except OSError:
                pass
            return None
        try:
            p.unlink()
        except OSError:
            pass
        if (time.time() - float(data.get("issued_at") or 0)) > self.ttl_seconds:
            return None
        known = {f.name for f in SSOPendingRecord.__dataclass_fields__.values()}
        return SSOPendingRecord(
            **{k: v for k, v in data.items() if k in known}
        )

    def purge_expired(self) -> int:
        now = time.time()
        removed = 0
        for f in self.root.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if (now - float(data.get("issued_at") or 0)) > self.ttl_seconds:
                try:
                    f.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed


__all__ = ["SSOPendingRecord", "SSOPendingStore"]
