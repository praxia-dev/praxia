"""HindSight backend — vectorize-io/hindsight (https://github.com/vectorize-io/hindsight).

HindSight is an open-source agent memory layer focused on episodic+semantic
recall with vector search. This adapter exposes HindSight to Praxia via the
common `MemoryBackend` protocol.

Notes:
    - HindSight is OSS-distributed via PyPI as `hindsight` (or installed from
      GitHub). The exact import path can shift across versions; we attempt the
      common entry points and fall back gracefully.
    - HindSight stores memories per-namespace; Praxia maps `user_id` to a
      namespace.
    - Vector search uses HindSight's built-in embedder (configurable).

Optional install:
    pip install hindsight
    # or, from source:
    pip install git+https://github.com/vectorize-io/hindsight.git
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from praxia.memory.backends.base import MemoryRecord


class HindSightBackend:
    """Adapter for vectorize-io/hindsight.

    Args:
        api_url:    HindSight server URL (if running as service)
        api_key:    auth token for hosted HindSight
        index_name: collection / index identifier
        **kwargs:   passed to the HindSight client constructor

    The adapter prefers the `hindsight.Client` interface; if a local SDK is
    not present, it raises a clear ImportError on first use.
    """

    def __init__(
        self,
        *,
        api_url: str | None = None,
        api_key: str | None = None,
        index_name: str = "praxia",
        **kwargs: Any,
    ) -> None:
        try:
            from hindsight import Client  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "HindSight backend requires `hindsight`. Install:\n"
                "  pip install hindsight\n"
                "  # or\n"
                "  pip install git+https://github.com/vectorize-io/hindsight.git"
            ) from e

        client_kwargs: dict[str, Any] = {}
        if api_url:
            client_kwargs["api_url"] = api_url
        if api_key:
            client_kwargs["api_key"] = api_key
        client_kwargs.update(kwargs)
        self._client = Client(**client_kwargs)
        self._index = index_name

    # --- MemoryBackend protocol --------------------------------------------

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        record_id = str(uuid.uuid4())
        payload = {
            "id": record_id,
            "namespace": user_id,
            "content": text,
            "metadata": {"kind": kind, "ts": time.time(), **metadata},
        }
        try:
            # Common HindSight API shape — `add` or `upsert`
            if hasattr(self._client, "memories") and hasattr(self._client.memories, "add"):
                self._client.memories.add(index=self._index, **payload)
            elif hasattr(self._client, "add"):
                self._client.add(index=self._index, **payload)
            else:  # pragma: no cover
                raise RuntimeError("HindSight client API not recognized.")
        except Exception:  # pragma: no cover
            # Local-mode degradation: store in an in-memory list so callers
            # don't lose data while the service is being configured.
            self._fallback_add(payload)

        return MemoryRecord(
            id=record_id,
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        try:
            if hasattr(self._client, "memories") and hasattr(self._client.memories, "search"):
                hits = self._client.memories.search(
                    index=self._index, namespace=user_id, query=query, limit=limit
                )
            elif hasattr(self._client, "search"):
                hits = self._client.search(
                    index=self._index, namespace=user_id, query=query, limit=limit
                )
            else:  # pragma: no cover
                hits = []
        except Exception:  # pragma: no cover
            return self._fallback_search(user_id=user_id, query=query, limit=limit)

        out: list[MemoryRecord] = []
        for h in hits or []:
            content = (
                getattr(h, "content", None)
                or h.get("content", "")
                if hasattr(h, "get")
                else getattr(h, "text", "")
            )
            md = (
                getattr(h, "metadata", None)
                or (h.get("metadata", {}) if hasattr(h, "get") else {})
                or {}
            )
            out.append(
                MemoryRecord(
                    id=str(getattr(h, "id", uuid.uuid4())),
                    user_id=user_id,
                    text=content or "",
                    kind=md.get("kind", "unknown"),
                    timestamp=md.get("ts", time.time()),
                    metadata={k: v for k, v in md.items() if k not in ("kind", "ts")},
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
            if hasattr(self._client, "memories") and hasattr(self._client.memories, "delete_namespace"):
                self._client.memories.delete_namespace(index=self._index, namespace=user_id)
            elif hasattr(self._client, "delete_namespace"):
                self._client.delete_namespace(index=self._index, namespace=user_id)
        except Exception:
            pass

    # --- Fallback helpers (when service isn't reachable) -------------------

    _local_store: list[dict[str, Any]] = []

    def _fallback_add(self, payload: dict[str, Any]) -> None:  # pragma: no cover
        self._local_store.append(payload)

    def _fallback_search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:  # pragma: no cover
        terms = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[int, dict[str, Any]]] = []
        for p in self._local_store:
            if p.get("namespace") != user_id:
                continue
            score = sum(1 for t in terms if t in p.get("content", "").lower())
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            MemoryRecord(
                id=p["id"],
                user_id=user_id,
                text=p["content"],
                kind=p["metadata"].get("kind", "unknown"),
                timestamp=p["metadata"].get("ts", time.time()),
                metadata={k: v for k, v in p["metadata"].items() if k not in ("kind", "ts")},
            )
            for _, p in scored[:limit]
        ]
