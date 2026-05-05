"""HTML / XML parser — strips tags using stdlib (no extra deps)."""
from __future__ import annotations

import html
import re
from typing import Any

from praxia.io.parsers.base import ParsedFile


class HtmlParser:
    name = "html"

    _TAG_RE = re.compile(r"<[^>]+>")
    _SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
    _WS_RE = re.compile(r"\s+")

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        text = data.decode("utf-8", errors="replace")
        # Strip <script> / <style> blocks first
        cleaned = self._SCRIPT_RE.sub("", text)
        # Remove all tags
        cleaned = self._TAG_RE.sub(" ", cleaned)
        # Decode HTML entities
        cleaned = html.unescape(cleaned)
        # Collapse whitespace
        cleaned = self._WS_RE.sub(" ", cleaned).strip()

        # Try to extract title for metadata
        title_match = re.search(
            r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL
        )
        title = title_match.group(1).strip() if title_match else None

        return ParsedFile(
            filename=filename,
            content=cleaned,
            metadata={"title": title, "raw_size": len(text)},
        )
