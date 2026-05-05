"""Exporter protocol + result container."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class Exporter(Protocol):
    """Anything that converts content to bytes for a target format."""

    format: str
    extensions: tuple[str, ...]

    def export(self, content: Any) -> bytes: ...


@dataclass
class ExporterResult:
    format: str
    bytes: bytes
    suggested_extension: str
    output_path: Path | None = None

    @property
    def size(self) -> int:
        return len(self.bytes)
