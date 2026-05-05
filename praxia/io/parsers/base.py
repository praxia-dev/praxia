"""Abstract file parser protocol + result type."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ParsedFile:
    """A file parsed into LLM-ready text + metadata.

    Attributes:
        filename: original filename (with extension)
        content:  primary text representation suitable for an LLM prompt
        metadata: format-specific metadata (page count, sheet names,
                  author, etc.)
        sections: optional list of (heading, text) sections — useful for
                  long PDFs where you want to preserve structure
    """

    filename: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[tuple[str, str]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.content)


class FileParser(Protocol):
    """All parsers implement this single method."""

    name: str

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        """Parse `data` (raw file bytes) into a `ParsedFile`."""
        ...
