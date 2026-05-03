"""Zep / Graphiti backend — temporal knowledge graph (Layer 5).

Use this only when relationships are the core business value: decision history,
customer 360, incident causal chains. For most uses, prefer mem0 or json.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from praxia.memory.backends.base import MemoryRecord


class ZepBackend:
    def __init__(
        self,
        *,
        api_url: str = "http://localhost:8000",
        api_key: str | None = None,
    ) -> None:
        try:
            from zep_python.client import Zep  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Zep backend requires `zep-python`. Install: pip install zep-python"
            ) from e
        self._client = Zep(api_url=api_url, api_key=api_key)

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        # Zep operates on session-based memory; we use user_id as the session.
        try:
            self._client.memory.add(
                session_id=user_id,
                messages=[{"role": "user", "content": text, "metadata": {"kind": kind, **metadata}}],
            )
        except Exception:  # pragma: no cover
            pass
        return MemoryRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        try:
            hits = self._client.memory.search(session_id=user_id, query=query, limit=limit)
        except Exception:  # pragma: no cover
            return []
        out: list[MemoryRecord] = []
        for h in hits or []:
            content = getattr(h, "content", "") or h.get("content", "")
            out.append(
                MemoryRecord(
                    id=str(getattr(h, "uuid", uuid.uuid4())),
                    user_id=user_id,
                    text=content,
                    kind="zep_episodic",
                    timestamp=time.time(),
                )
            )
        return out

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:  # pragma: no cover
        if not user_id:
            return []
        return self.search(user_id=user_id, query="", limit=10_000)

    def clear(self, *, user_id: str | None = None) -> None:  # pragma: no cover
        if not user_id:
            return
        try:
            self._client.memory.delete(session_id=user_id)
        except Exception:
            pass
