"""Abstract LTM backend protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class MemoryRecord:
    id: str
    user_id: str
    text: str
    kind: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryBackend(Protocol):
    """Every LTM backend must implement these four operations."""

    def add(self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]) -> MemoryRecord:
        ...

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        ...

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        ...

    def clear(self, *, user_id: str | None = None) -> None:
        ...
