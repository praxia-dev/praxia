"""Personal memory layer (Layer 1) — pluggable LTM backend wrapper.

Auto-extracts tacit knowledge from conversations and flow runs without explicit
save operations. The actual storage backend is pluggable: choose between
JSON (default), Mem0, LangMem, Letta, or Zep at construction time.

Example:
    pm = PersonalMemory(user_id="alice", backend="mem0")
    pm = PersonalMemory(user_id="alice", backend="json")  # default
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentloom.memory.backends import MemoryBackend, MemoryRecord, load_backend


@dataclass
class MemoryEntry:
    """User-facing record (decoupled from any specific backend)."""
    id: str
    user_id: str
    text: str
    kind: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_record(cls, r: MemoryRecord) -> MemoryEntry:
        return cls(
            id=r.id,
            user_id=r.user_id,
            text=r.text,
            kind=r.kind,
            timestamp=r.timestamp,
            metadata=r.metadata,
        )


class PersonalMemory:
    """Layer-1 personal memory with pluggable LTM backend.

    Args:
        user_id: namespace key for this user's memories.
        backend: "json" (default) | "mem0" | "langmem" | "letta" | "zep"
                 or a pre-built MemoryBackend instance.
        storage_dir: only used by file-based backends (json).
        **backend_kwargs: passed through to the backend constructor.

    Env vars:
        AGENTLOOM_MEMORY_BACKEND — overrides backend if not explicitly given.
    """

    def __init__(
        self,
        user_id: str,
        *,
        backend: str | MemoryBackend = "auto",
        storage_dir: Path | str | None = None,
        **backend_kwargs: Any,
    ) -> None:
        self.user_id = user_id

        if isinstance(backend, str):
            if backend == "auto":
                backend = os.getenv("AGENTLOOM_MEMORY_BACKEND", "json")
            if backend == "json" and storage_dir is not None:
                backend_kwargs.setdefault("storage_dir", storage_dir)
            self._backend: MemoryBackend = load_backend(backend, **backend_kwargs)
        else:
            self._backend = backend

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__

    def record_episode(
        self,
        *,
        flow_name: str,
        inputs: dict[str, Any],
        output: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        text = (
            f"[{flow_name}] inputs={json.dumps(inputs, ensure_ascii=False)[:500]} "
            f"output={output[:500]}"
        )
        rec = self._backend.add(
            user_id=self.user_id,
            text=text,
            kind="episode",
            metadata=metadata or {},
        )
        return MemoryEntry.from_record(rec)

    def record_fact(
        self, text: str, *, metadata: dict[str, Any] | None = None
    ) -> MemoryEntry:
        rec = self._backend.add(
            user_id=self.user_id, text=text, kind="fact", metadata=metadata or {}
        )
        return MemoryEntry.from_record(rec)

    def record_preference(
        self, text: str, *, metadata: dict[str, Any] | None = None
    ) -> MemoryEntry:
        rec = self._backend.add(
            user_id=self.user_id, text=text, kind="preference", metadata=metadata or {}
        )
        return MemoryEntry.from_record(rec)

    def search(self, query: str, limit: int = 5) -> list[str]:
        records = self._backend.search(user_id=self.user_id, query=query, limit=limit)
        return [r.text for r in records]

    def all_entries(self) -> list[MemoryEntry]:
        return [MemoryEntry.from_record(r) for r in self._backend.all(user_id=self.user_id)]

    def clear(self) -> None:
        self._backend.clear(user_id=self.user_id)
