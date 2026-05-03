"""Shared memory layer (Layer 3).

Letta-style "shared memory blocks" — labeled chunks of organizational knowledge
that all agents read and selectively write. Each block has an access policy
(`read_write` | `read_only`) so policy-style content can't be mutated by agents.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

AccessMode = Literal["read_write", "read_only"]


@dataclass
class SharedBlock:
    id: str
    label: str
    description: str
    value: str
    access: AccessMode = "read_write"
    promoted_from: list[str] = field(default_factory=list)  # contributing user IDs
    promoted_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)


class SharedMemory:
    """Organizational shared memory blocks (Layer 3 of the 5-layer stack)."""

    def __init__(self, org_id: str, storage_dir: Path) -> None:
        self.org_id = org_id
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.storage_dir / f"{org_id}.jsonl"

    def upsert(
        self,
        *,
        label: str,
        description: str,
        value: str,
        access: AccessMode = "read_write",
        promoted_from: list[str] | None = None,
    ) -> SharedBlock:
        existing = self.get_by_label(label)
        block = SharedBlock(
            id=existing.id if existing else str(uuid.uuid4()),
            label=label,
            description=description,
            value=value,
            access=access,
            promoted_from=promoted_from or (existing.promoted_from if existing else []),
        )
        self._save_all([b for b in self.list_all() if b.label != label] + [block])
        return block

    def get_by_label(self, label: str) -> SharedBlock | None:
        for block in self.list_all():
            if block.label == label:
                return block
        return None

    def list_all(self) -> list[SharedBlock]:
        if not self.path.exists():
            return []
        out: list[SharedBlock] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(SharedBlock(**json.loads(line)))
                except json.JSONDecodeError:
                    continue
        return out

    def search(self, *, query: str, limit: int = 5) -> list[str]:
        terms = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[int, SharedBlock]] = []
        for block in self.list_all():
            haystack = (block.label + " " + block.description + " " + block.value).lower()
            score = sum(1 for t in terms if t in haystack)
            if score:
                scored.append((score, block))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f"[{b.label}] {b.value}" for _, b in scored[:limit]]

    def append_to_block(self, label: str, addition: str) -> SharedBlock:
        block = self.get_by_label(label)
        if not block:
            return self.upsert(label=label, description=label, value=addition)
        if block.access == "read_only":
            raise PermissionError(f"Block '{label}' is read-only.")
        block.value = block.value + "\n" + addition
        self._save_all(
            [b for b in self.list_all() if b.label != label] + [block]
        )
        return block

    def _save_all(self, blocks: list[SharedBlock]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(asdict(block), ensure_ascii=False) + "\n")

    def remove(self, label: str) -> None:
        self._save_all([b for b in self.list_all() if b.label != label])
