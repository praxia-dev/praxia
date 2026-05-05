"""Microsoft PowerPoint (.pptx) parser — uses python-pptx."""
from __future__ import annotations

import io
from typing import Any

from praxia.io.parsers.base import ParsedFile


class PptxParser:
    name = "pptx"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        try:
            from pptx import Presentation
        except ImportError as e:
            raise ImportError(
                "PowerPoint (.pptx) parsing requires `python-pptx`. Install with:\n"
                '  pip install "praxia[office]"'
            ) from e

        prs = Presentation(io.BytesIO(data))
        sections: list[tuple[str, str]] = []
        full_text: list[str] = []

        for i, slide in enumerate(prs.slides, start=1):
            slide_lines: list[str] = []
            slide_title: str | None = None

            for shape in slide.shapes:
                # Title
                if shape.has_text_frame:
                    tf = shape.text_frame
                    text = tf.text.strip()
                    if not text:
                        continue
                    if (
                        slide_title is None
                        and getattr(shape, "is_placeholder", False)
                        and "title" in str(shape.placeholder_format.type or "").lower()
                    ):
                        slide_title = text
                    slide_lines.append(text)
                # Tables in slides
                if shape.has_table:
                    rows: list[list[str]] = []
                    for row in shape.table.rows:
                        rows.append([cell.text.strip() for cell in row.cells])
                    if rows:
                        slide_lines.append(
                            "| " + " | ".join(rows[0]) + " |"
                        )
                        slide_lines.append(
                            "|" + "|".join(["---"] * len(rows[0])) + "|"
                        )
                        for row in rows[1:]:
                            slide_lines.append("| " + " | ".join(row) + " |")
                # Notes
            notes_text = ""
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()

            heading = slide_title or f"Slide {i}"
            section_body = "\n".join(slide_lines)
            if notes_text:
                section_body += f"\n\n[Speaker notes]\n{notes_text}"
            sections.append((heading, section_body))

            full_text.append(f"\n## Slide {i}: {heading}\n{section_body}")

        return ParsedFile(
            filename=filename,
            content="\n".join(full_text),
            metadata={
                "slide_count": len(prs.slides),
            },
            sections=sections,
        )
