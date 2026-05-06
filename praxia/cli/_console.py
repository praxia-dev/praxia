"""Shared Rich Console for CLI commands.

Defining `console` once and importing it everywhere keeps output styling
consistent and avoids each command module instantiating its own.
"""
from __future__ import annotations

from rich.console import Console

console = Console()

__all__ = ["console"]
