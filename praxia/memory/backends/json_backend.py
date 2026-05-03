"""Default JSONL on-disk backend. Zero external deps."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from praxia.memory.backends.base import MemoryRecord


class JsonBackend:
    """Append-only JSONL store. One file per user_id.

    Trade-offs:
      - Pros: zero deps, fully auditable, trivial to back up.
      - Cons: BM25-style term overlap search (no embeddings).
              Use Mem0 / LangMem for semantic recall.
    """

    def __init__(self, *, storage_dir: Path | str = ".praxia/memory") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        return self.storage_dir / f"{user_id}.jsonl"

    def add(
        self, *, user_id: str, text: str, kind: str, metadata: dict[str, Any]
    ) -> MemoryRecord:
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            text=text,
            kind=kind,
            timestamp=time.time(),
            metadata=metadata,
        )
        with self._path(user_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return record

    def search(self, *, user_id: str, query: str, limit: int) -> list[MemoryRecord]:
        path = self._path(user_id)
        if not path.exists():
            return []
        terms = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[int, MemoryRecord]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = MemoryRecord(**json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue
                score = sum(1 for t in terms if t in rec.text.lower())
                if score:
                    scored.append((score, rec))
        scored.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)
        return [r for _, r in scored[:limit]]

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        files = (
            [self._path(user_id)] if user_id else list(self.storage_dir.glob("*.jsonl"))
        )
        for path in files:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(MemoryRecord(**json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue
        return out

    def clear(self, *, user_id: str | None = None) -> None:
        if user_id:
            path = self._path(user_id)
            if path.exists():
                path.unlink()
        else:
            for path in self.storage_dir.glob("*.jsonl"):
                path.unlink()
