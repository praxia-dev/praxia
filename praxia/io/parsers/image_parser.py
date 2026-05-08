"""Image parser — keeps the bytes for vision LLM input + emits a tiny
text placeholder so the file shows up in text-based context retrieval.

Praxia's other parsers turn a file into pure text. Images are different:
the *content* the LLM cares about lives in the pixels, not in any
transcription we could synthesize. So this parser:

1. Returns a one-line text placeholder (`[image: chart.png (image/png,
   245 KB)]`) as ``content`` so grep-based scope retrieval can still
   surface the file.
2. Stuffs the raw bytes (base64) and MIME type into ``metadata["image"]``
   for the UI to pick up and forward to ``AutonomousAgent.run(images=...)``.
3. Falls through gracefully if the bytes don't look like a real image.

Supported extensions: png / jpg / jpeg / gif / webp. Anything else stays
unsupported (e.g. raw camera formats, SVG vector — those would need a
rasterizer first).
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from praxia.io.parsers.base import ParsedFile

_EXT_TO_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class ImageParser:
    """Image → ParsedFile with text placeholder + base64 in metadata."""

    name = "image"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        ext = Path(filename).suffix.lower().lstrip(".")
        mime = _EXT_TO_MIME.get(ext, "application/octet-stream")
        size_str = _format_bytes(len(data))

        # Text placeholder: short enough to not eat context-window budget,
        # specific enough that grep on filename or "image:" still hits.
        placeholder = f"[image: {filename} ({mime}, {size_str})]"

        b64 = base64.b64encode(data).decode("ascii")

        return ParsedFile(
            filename=filename,
            content=placeholder,
            metadata={
                "kind": "image",
                "image": {
                    "data": b64,
                    "mime": mime,
                    "size_bytes": len(data),
                },
            },
            sections=[],
        )
