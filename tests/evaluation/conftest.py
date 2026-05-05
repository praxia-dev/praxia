"""Shared fixtures for the evaluation suite."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_storage():
    """Disposable .praxia/-style storage directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def stub_backend_factory():
    """Build a stub MemoryBackend with a fixed result list."""
    from praxia.memory.backends.base import MemoryRecord

    def _factory(records=None, *, on_search_raise=False, name="stub"):
        records = records or []
        captured = {"add_calls": 0, "search_calls": 0}

        class StubBackend:
            def __init__(self):
                self._records = list(records)

            def add(self, *, user_id, text, kind, metadata):
                captured["add_calls"] += 1
                rec = MemoryRecord(
                    id=f"{name}-{captured['add_calls']}",
                    user_id=user_id,
                    text=text,
                    kind=kind,
                    timestamp=1.0,
                    metadata=metadata,
                )
                self._records.append(rec)
                return rec

            def search(self, *, user_id, query, limit):
                captured["search_calls"] += 1
                if on_search_raise:
                    raise RuntimeError(f"{name} search forced failure")
                return self._records[:limit]

            def all(self, *, user_id=None):
                return list(self._records)

            def clear(self, *, user_id=None):
                self._records.clear()

        return StubBackend(), captured

    return _factory


@pytest.fixture
def make_record():
    """Build a MemoryRecord with sensible defaults."""
    from praxia.memory.backends.base import MemoryRecord

    def _factory(rid, *, text="", kind="fact", user_id="u", ts=1.0):
        return MemoryRecord(
            id=rid, user_id=user_id, text=text or rid, kind=kind, timestamp=ts
        )

    return _factory
