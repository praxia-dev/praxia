"""CSV / TSV parser — converts to Markdown-style table for the LLM."""
from __future__ import annotations

import csv
import io
from typing import Any

from praxia.io.parsers.base import ParsedFile


class CsvParser:
    name = "csv"

    def parse(
        self,
        data: bytes,
        *,
        filename: str,
        max_rows: int = 1000,
        **kwargs: Any,
    ) -> ParsedFile:
        delim = "\t" if filename.lower().endswith(".tsv") else ","
        # Try UTF-8 with BOM tolerance, then Shift-JIS for JP exports
        text: str = ""
        for encoding in ("utf-8-sig", "utf-8", "shift_jis", "cp932", "latin-1"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        reader = csv.reader(io.StringIO(text), delimiter=delim)
        rows = list(reader)
        if not rows:
            return ParsedFile(filename=filename, content="(empty file)")

        header = rows[0]
        body = rows[1 : 1 + max_rows]
        truncated = len(rows) - 1 > max_rows

        # Render as a Markdown table — concise and LLM-friendly
        md_lines: list[str] = []
        md_lines.append("| " + " | ".join(header) + " |")
        md_lines.append("|" + "|".join(["---"] * len(header)) + "|")
        for row in body:
            # Pad short rows so the markdown stays valid
            padded = row + [""] * (len(header) - len(row))
            md_lines.append("| " + " | ".join(padded[: len(header)]) + " |")
        if truncated:
            md_lines.append(
                f"\n_(showing first {max_rows} of {len(rows) - 1} rows)_"
            )

        return ParsedFile(
            filename=filename,
            content="\n".join(md_lines),
            metadata={
                "rows": len(rows) - 1,
                "columns": len(header),
                "header": header,
                "truncated": truncated,
            },
        )
