"""Plain-text parser — txt, md, rst, py, ts, js, etc."""
from __future__ import annotations

from typing import Any

from praxia.io.parsers.base import ParsedFile


class TextParser:
    name = "text"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        # Try common encodings — UTF-8 first, then Shift-JIS for legacy JP files
        for encoding in ("utf-8", "utf-8-sig", "shift_jis", "cp932", "latin-1"):
            try:
                content = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            content = data.decode("utf-8", errors="replace")
        return ParsedFile(
            filename=filename,
            content=content,
            metadata={"encoding": encoding, "size": len(data)},
        )
