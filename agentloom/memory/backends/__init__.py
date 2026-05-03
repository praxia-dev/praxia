"""Pluggable LTM backends.

Out-of-the-box options:
    - "json"     — simple on-disk JSONL (default, no extra deps)
    - "mem0"     — Mem0 OSS (entity linking + hybrid search)
    - "langmem"  — LangChain LangMem SDK
    - "letta"    — Letta shared blocks (also usable as personal store)
    - "zep"      — Zep / Graphiti for temporal KG (Layer 5)

Choose at construction time:

    PersonalMemory(user_id="alice", backend="mem0")

Or via env var:

    AGENTLOOM_MEMORY_BACKEND=mem0
"""
from agentloom.memory.backends.base import MemoryBackend, MemoryRecord
from agentloom.memory.backends.json_backend import JsonBackend

__all__ = ["MemoryBackend", "MemoryRecord", "JsonBackend", "load_backend"]


def load_backend(name: str, **kwargs) -> MemoryBackend:
    """Factory. Imports lazily so optional deps stay optional."""
    name = (name or "json").lower()
    if name == "json":
        return JsonBackend(**kwargs)
    if name == "mem0":
        from agentloom.memory.backends.mem0_backend import Mem0Backend

        return Mem0Backend(**kwargs)
    if name == "langmem":
        from agentloom.memory.backends.langmem_backend import LangMemBackend

        return LangMemBackend(**kwargs)
    if name == "letta":
        from agentloom.memory.backends.letta_backend import LettaBackend

        return LettaBackend(**kwargs)
    if name == "zep":
        from agentloom.memory.backends.zep_backend import ZepBackend

        return ZepBackend(**kwargs)
    raise ValueError(
        f"Unknown memory backend: {name!r}. "
        f"Supported: json, mem0, langmem, letta, zep"
    )
