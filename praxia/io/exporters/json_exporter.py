"""JSON exporter — for when the caller wants structured data, not text."""
from __future__ import annotations

import json
from typing import Any


class JsonExporter:
    format = "json"
    extensions = ("json",)

    def __init__(self, *, indent: int = 2, ensure_ascii: bool = False) -> None:
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def export(self, content: Any) -> bytes:
        if isinstance(content, str):
            payload: Any = {"text": content}
        else:
            payload = content
        return json.dumps(
            payload, indent=self.indent, ensure_ascii=self.ensure_ascii, default=str
        ).encode("utf-8")
