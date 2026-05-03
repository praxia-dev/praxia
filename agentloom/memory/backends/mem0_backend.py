"""Mem0 backend — entity linking + hybrid search.

Recommended when you want semantic recall over conversations. Mem0 OSS handles
auto-extraction of facts/preferences/episodes, multi-language support, and
hybrid search (BM25 + dense vectors + entity linking).

Note: Mem0 dropped graph_store support in 2026-04 — we mirror that decision and
do not invoke any graph features here. Use the Zep backend if you need a
temporal KG.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from agentloom.memory.backends.base import MemoryRecord


class Mem0Backend:
    def __init__(self, **mem0_kwargs: Any) -> None:
        try:
            from mem0 import Memory  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Mem0 backend requires `mem0ai`. Install: pip install mem0ai"
            ) from e
        self._memory = Memory(**mem0_kwargs) if mem0_kwargs else Memory()

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        result = self._memory.add(
            messages=[{"role": "user", "content": text}],
            user_id=user_id,
            metadata={"kind": kind, **metadata},
        )
        record_id = result.get("results", [{}])[0].get("id", str(uuid.uuid4()))
        return MemoryRecord(
            id=str(record_id),
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        hits = self._memory.search(query=query, user_id=user_id, limit=limit)
        out: list[MemoryRecord] = []
        for h in hits.get("results", []):
            out.append(
                MemoryRecord(
                    id=str(h.get("id", "")),
                    user_id=user_id,
                    text=h.get("memory", ""),
                    kind=h.get("metadata", {}).get("kind", "unknown"),
                    timestamp=h.get("created_at", time.time()) or time.time(),
                    metadata=h.get("metadata", {}),
                )
            )
        return out

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        if not user_id:
            return []
        items = self._memory.get_all(user_id=user_id)
        out: list[MemoryRecord] = []
        for h in items.get("results", []):
            out.append(
                MemoryRecord(
                    id=str(h.get("id", "")),
                    user_id=user_id,
                    text=h.get("memory", ""),
                    kind=h.get("metadata", {}).get("kind", "unknown"),
                    timestamp=h.get("created_at", time.time()) or time.time(),
                    metadata=h.get("metadata", {}),
                )
            )
        return out

    def clear(self, *, user_id: str | None = None) -> None:
        if user_id:
            self._memory.delete_all(user_id=user_id)
