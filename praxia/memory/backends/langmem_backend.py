"""LangMem backend — LangChain's long-term memory SDK.

Useful when you already use the LangChain stack and want namespace-aware
memory blocks (user / team / org). Lazy-imported so the dep is optional.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from praxia.memory.backends.base import MemoryRecord


class LangMemBackend:
    def __init__(self, *, namespace: str = "praxia", **kwargs: Any) -> None:
        try:
            from langmem import create_memory_store  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "LangMem backend requires `langmem`. Install: pip install langmem"
            ) from e
        self._namespace = namespace
        self._store = create_memory_store(namespace=namespace, **kwargs)

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        record_id = str(uuid.uuid4())
        self._store.put(
            ((self._namespace, user_id), record_id),
            {"text": text, "kind": kind, **metadata},
        )
        return MemoryRecord(
            id=record_id,
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        results = self._store.search((self._namespace, user_id), query=query, limit=limit)
        out: list[MemoryRecord] = []
        for r in results:
            value = r.value if hasattr(r, "value") else r.get("value", {})
            out.append(
                MemoryRecord(
                    id=getattr(r, "key", "") or r.get("key", ""),
                    user_id=user_id,
                    text=value.get("text", ""),
                    kind=value.get("kind", "unknown"),
                    timestamp=value.get("timestamp", time.time()),
                    metadata={k: v for k, v in value.items() if k not in ("text", "kind", "timestamp")},
                )
            )
        return out

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        if not user_id:
            return []
        return self.search(user_id=user_id, query="", limit=10_000)

    def clear(self, *, user_id: str | None = None) -> None:  # pragma: no cover
        if user_id and hasattr(self._store, "delete_namespace"):
            self._store.delete_namespace((self._namespace, user_id))
