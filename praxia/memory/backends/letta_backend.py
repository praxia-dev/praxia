"""Letta backend — uses Letta's memory blocks as the LTM store.

Best when you need shared/personal memory blocks with read_only policies, or
when you'll run Letta sleep-time agents alongside Praxia's own
consolidator.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from praxia.memory.backends.base import MemoryRecord


class LettaBackend:
    def __init__(
        self,
        *,
        base_url: str = "http://localhost:8283",
        api_key: str | None = None,
        block_label_template: str = "praxia_{user_id}",
    ) -> None:
        try:
            from letta_client import Letta  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Letta backend requires `letta-client`. Install: pip install letta-client"
            ) from e
        self._client = Letta(base_url=base_url, token=api_key) if api_key else Letta(base_url=base_url)
        self._template = block_label_template

    def _block_label(self, user_id: str) -> str:
        return self._template.format(user_id=user_id)

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        label = self._block_label(user_id)
        try:
            block = self._client.blocks.retrieve(block_label=label)
            new_value = (block.value or "") + f"\n[{kind}] {text}"
            self._client.blocks.update(block_id=block.id, value=new_value)
        except Exception:
            self._client.blocks.create(label=label, value=f"[{kind}] {text}")
        return MemoryRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        label = self._block_label(user_id)
        try:
            block = self._client.blocks.retrieve(block_label=label)
        except Exception:
            return []
        terms = {t.lower() for t in query.split() if len(t) > 2}
        out: list[MemoryRecord] = []
        for line in (block.value or "").splitlines():
            if any(t in line.lower() for t in terms):
                out.append(
                    MemoryRecord(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        text=line,
                        kind="block_line",
                        timestamp=time.time(),
                    )
                )
            if len(out) >= limit:
                break
        return out

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        if not user_id:
            return []
        return self.search(user_id=user_id, query="", limit=10_000)

    def clear(self, *, user_id: str | None = None) -> None:  # pragma: no cover
        if not user_id:
            return
        label = self._block_label(user_id)
        try:
            block = self._client.blocks.retrieve(block_label=label)
            self._client.blocks.delete(block_id=block.id)
        except Exception:
            pass
