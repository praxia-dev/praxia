"""PDF parser — uses pypdf (pure Python, no native deps)."""
from __future__ import annotations

import io
from typing import Any

from praxia.io.parsers.base import ParsedFile


class PdfParser:
    name = "pdf"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError(
                "PDF parsing requires `pypdf`. Install with:\n"
                '  pip install "praxia[office]"'
            ) from e

        reader = PdfReader(io.BytesIO(data))
        sections: list[tuple[str, str]] = []
        full_text: list[str] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            sections.append((f"Page {i}", page_text))
            full_text.append(f"--- Page {i} ---\n{page_text}")

        meta = reader.metadata
        return ParsedFile(
            filename=filename,
            content="\n\n".join(full_text),
            metadata={
                "page_count": len(reader.pages),
                "title": (str(meta.title) if meta and meta.title else None),
                "author": (str(meta.author) if meta and meta.author else None),
                "encrypted": reader.is_encrypted,
            },
            sections=sections,
        )
