"""Optional FastAPI HTTP server.

Use when your frontend is not Python — wraps the SDK behind versioned REST
endpoints. See `docs/deployment-modes.md`.

Requires `pip install 'praxia[server]'` (FastAPI + uvicorn).
"""
from __future__ import annotations

__all__ = ["create_app"]


def create_app(*args, **kwargs):
    """Lazy factory — defers FastAPI import to actual `serve` invocation."""
    from praxia.server.app import create_app as _impl
    return _impl(*args, **kwargs)
