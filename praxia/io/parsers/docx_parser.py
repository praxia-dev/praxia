"""Microsoft Word (.docx) parser — uses python-docx."""
from __future__ import annotations

import io
from typing import Any

from praxia.io.parsers.base import ParsedFile


class DocxParser:
    name = "docx"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        try:
            import docx
        except ImportError as e:
            raise ImportError(
                "Word (.docx) parsing requires `python-docx`. Install with:\n"
                '  pip install "praxia[office]"'
            ) from e

        doc = docx.Document(io.BytesIO(data))

        # Extract paragraphs with style for structure preservation
        sections: list[tuple[str, str]] = []
        current_heading = "Body"
        body_lines: list[str] = []
        full_text: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "").lower() if para.style else ""
            if "heading" in style:
                # Flush previous section
                if body_lines:
                    sections.append((current_heading, "\n".join(body_lines)))
                    body_lines = []
                current_heading = text
                full_text.append(f"\n## {text}\n")
            else:
                body_lines.append(text)
                full_text.append(text)

        # Flush last section
        if body_lines:
            sections.append((current_heading, "\n".join(body_lines)))

        # Extract tables as Markdown
        for i, table in enumerate(doc.tables, start=1):
            rows = []
            for row in table.rows:
                rows.append([cell.text.strip() for cell in row.cells])
            if rows:
                full_text.append(f"\n### Table {i}\n")
                full_text.append("| " + " | ".join(rows[0]) + " |")
                full_text.append("|" + "|".join(["---"] * len(rows[0])) + "|")
                for row in rows[1:]:
                    full_text.append("| " + " | ".join(row) + " |")

        return ParsedFile(
            filename=filename,
            content="\n".join(full_text),
            metadata={
                "paragraph_count": len(doc.paragraphs),
                "table_count": len(doc.tables),
                "section_count": len(sections),
            },
            sections=sections,
        )
