"""Pluggable LTM backends — uses praxia.extensions.Registry.

Out-of-the-box options:
    - "json"      — simple on-disk JSONL (default, no extra deps)
    - "mem0"      — Mem0 OSS (entity linking + hybrid search)
    - "langmem"   — LangChain LangMem SDK
    - "letta"     — Letta shared blocks (also usable as personal store)
    - "zep"       — Zep / Graphiti for temporal KG (Layer 5)
    - "hindsight" — vectorize-io/hindsight agent memory store

To add a custom backend:

    1. Implement the `MemoryBackend` protocol (4 methods: add/search/all/clear)
    2. Either:
       a. `@BACKENDS.register_decorator("my_backend")`
       b. Or a pyproject.toml entry-point:
          [project.entry-points."praxia.memory_backends"]
          my_backend = "my_pkg.my_backend:MyBackend"

Choose at construction time:

    PersonalMemory(user_id="alice", backend="mem0")

Or via env var:

    PRAXIA_MEMORY_BACKEND=mem0
"""
from __future__ import annotations

from typing import Any

from praxia.extensions import Registry, lazy
from praxia.memory.backends.base import MemoryBackend, MemoryRecord
from praxia.memory.backends.json_backend import JsonBackend

BACKENDS: Registry[MemoryBackend] = Registry(
    name="memory backend",
    entry_point_group="praxia.memory_backends",
)

# Built-in registrations
BACKENDS.register("json", JsonBackend)
BACKENDS.register("mem0", lazy("praxia.memory.backends.mem0_backend:Mem0Backend"))
BACKENDS.register("langmem", lazy("praxia.memory.backends.langmem_backend:LangMemBackend"))
BACKENDS.register("letta", lazy("praxia.memory.backends.letta_backend:LettaBackend"))
BACKENDS.register("zep", lazy("praxia.memory.backends.zep_backend:ZepBackend"))
BACKENDS.register("hindsight", lazy("praxia.memory.backends.hindsight_backend:HindSightBackend"))


__all__ = ["MemoryBackend", "MemoryRecord", "JsonBackend", "BACKENDS", "load_backend"]


def load_backend(name: str, **kwargs: Any) -> MemoryBackend:
    """Factory. Imports lazily so optional deps stay optional."""
    name = (name or "json").lower()
    try:
        cls = BACKENDS.get(name)
    except KeyError:
        raise ValueError(
            f"Unknown memory backend: {name!r}. "
            f"Supported: {', '.join(BACKENDS.list())}"
        )
    return cls(**kwargs)
