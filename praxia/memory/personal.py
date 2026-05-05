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
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from praxia.memory.backends import MemoryBackend, MemoryRecord, load_backend

_log = logging.getLogger(__name__)

MemoryMode = Literal["accumulate", "read_only"]


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
        mode: "accumulate" (default — writes go through) or "read_only"
              (writes are silently dropped, reads still work). Admin
              policy may override and lock this — see `praxia.memory.policy`.
        **backend_kwargs: passed through to the backend constructor.

    Env vars:
        PRAXIA_MEMORY_BACKEND — overrides backend if not explicitly given.
        PRAXIA_MEMORY_MODE    — overrides mode if not explicitly given.
    """

    def __init__(
        self,
        user_id: str,
        *,
        backend: str | MemoryBackend = "auto",
        storage_dir: Path | str | None = None,
        mode: MemoryMode | None = None,
        **backend_kwargs: Any,
    ) -> None:
        self.user_id = user_id

        if isinstance(backend, str):
            if backend == "auto":
                backend = os.getenv("PRAXIA_MEMORY_BACKEND", "json")
            if backend == "json" and storage_dir is not None:
                backend_kwargs.setdefault("storage_dir", storage_dir)
            self._backend: MemoryBackend = load_backend(backend, **backend_kwargs)
        else:
            self._backend = backend

        if mode is None:
            env_mode = os.getenv("PRAXIA_MEMORY_MODE")
            mode = env_mode if env_mode in ("accumulate", "read_only") else "accumulate"
        self._mode: MemoryMode = mode

    @property
    def backend_name(self) -> str:
        return type(self._backend).__name__

    @property
    def mode(self) -> MemoryMode:
        return self._mode

    def set_mode(self, mode: MemoryMode) -> None:
        """Switch between 'accumulate' (writes pass through) and 'read_only'."""
        if mode not in ("accumulate", "read_only"):
            raise ValueError(f"Invalid memory mode: {mode!r}")
        self._mode = mode

    def _drop_for_read_only(self, kind: str) -> MemoryEntry:
        """Return a transient entry without persisting (read-only mode)."""
        _log.debug(
            "memory mode=read_only: dropping %s write for user %s", kind, self.user_id
        )
        # Use a deterministic prefix so callers can detect the no-op.
        return MemoryEntry(
            id=f"readonly:{kind}",
            user_id=self.user_id,
            text="",
            kind=kind,
            timestamp=0.0,
            metadata={"read_only_dropped": True},
        )

    def record_episode(
        self,
        *,
        flow_name: str,
        inputs: dict[str, Any],
        output: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        if self._mode == "read_only":
            return self._drop_for_read_only("episode")
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
        if self._mode == "read_only":
            return self._drop_for_read_only("fact")
        rec = self._backend.add(
            user_id=self.user_id, text=text, kind="fact", metadata=metadata or {}
        )
        return MemoryEntry.from_record(rec)

    def record_preference(
        self, text: str, *, metadata: dict[str, Any] | None = None
    ) -> MemoryEntry:
        if self._mode == "read_only":
            return self._drop_for_read_only("preference")
        rec = self._backend.add(
            user_id=self.user_id, text=text, kind="preference", metadata=metadata or {}
        )
        return MemoryEntry.from_record(rec)

    def record_outcome(
        self,
        *,
        episode_id: str,
        success: bool,
        score: float | None = None,
        notes: str = "",
    ) -> MemoryEntry:
        """Phase 2: attach an outcome to a previously recorded episode.

        Outcomes are what enable **statistical promotion** in the consolidator:
        a pattern that correlates with successes (won deals, accepted PRs,
        passing tests, etc.) gets weighted higher when judging org-promotion.

        Args:
            episode_id: id returned from a prior `record_episode()` call
            success: True if the action led to a positive outcome
            score: optional numeric score (e.g., revenue won, % improvement)
            notes: free-form annotation
        """
        if self._mode == "read_only":
            return self._drop_for_read_only("outcome")
        text = f"[outcome:episode={episode_id}] success={success} score={score} {notes}"
        rec = self._backend.add(
            user_id=self.user_id,
            text=text,
            kind="outcome",
            metadata={
                "episode_id": episode_id,
                "success": success,
                "score": score,
                "notes": notes,
            },
        )
        return MemoryEntry.from_record(rec)

    def outcomes_for(self, episode_id: str) -> list[MemoryEntry]:
        """Retrieve outcome records linked to a given episode."""
        return [
            e
            for e in self.all_entries()
            if e.kind == "outcome" and e.metadata.get("episode_id") == episode_id
        ]

    def search(self, query: str, limit: int = 5) -> list[str]:
        records = self._backend.search(user_id=self.user_id, query=query, limit=limit)
        return [r.text for r in records]

    def all_entries(self) -> list[MemoryEntry]:
        return [MemoryEntry.from_record(r) for r in self._backend.all(user_id=self.user_id)]

    def clear(self) -> None:
        self._backend.clear(user_id=self.user_id)
