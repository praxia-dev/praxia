"""JSON / YAML parser — pretty-printed for LLM context."""
from __future__ import annotations

import json
from typing import Any

from praxia.io.parsers.base import ParsedFile


class StructuredParser:
    name = "structured"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        text = data.decode("utf-8", errors="replace")
        ext = filename.rsplit(".", 1)[-1].lower()
        try:
            if ext in ("yaml", "yml"):
                import yaml  # part of core deps
                obj = yaml.safe_load(text)
            else:
                obj = json.loads(text)
            pretty = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
            return ParsedFile(
                filename=filename,
                content=pretty,
                metadata={
                    "format": ext,
                    "is_valid": True,
                    "top_level_keys": (
                        list(obj.keys()) if isinstance(obj, dict) else []
                    ),
                },
            )
        except Exception as e:
            # Fallback: just include the raw text plus the error
            return ParsedFile(
                filename=filename,
                content=text,
                metadata={"format": ext, "is_valid": False, "parse_error": str(e)},
            )
