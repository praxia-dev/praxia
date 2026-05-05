"""PPTX exporter — converts Markdown into a slide deck.

Heuristics:
    - First `# Title` becomes the title slide.
    - Each `## Section` starts a new content slide.
    - Bullet lists under a section become bullets on that slide.
    - Plain paragraphs become a single text bullet.

Requires `python-pptx` (install via `pip install praxia[office]`).
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Any


class PptxExporter:
    format = "pptx"
    extensions = ("pptx",)

    def __init__(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.author = author

    def export(self, content: Any) -> bytes:
        try:
            from pptx import Presentation
            from pptx.util import Pt
        except ImportError as e:
            raise ImportError(
                "python-pptx is required for PPTX export. "
                "Install with: pip install 'praxia[office]'"
            ) from e

        if isinstance(content, dict):
            content = self._dict_to_md(content)
        elif not isinstance(content, str):
            content = str(content)

        prs = Presentation()
        slides = self._segment(content)

        # Title slide (always first)
        title_slide = prs.slides.add_slide(prs.slide_layouts[0])
        if title_slide.placeholders[0].has_text_frame:
            title_slide.placeholders[0].text = self.title or slides[0]["title"] or "Praxia Output"
        if len(title_slide.placeholders) > 1 and self.subtitle:
            title_slide.placeholders[1].text = self.subtitle

        # Content slides — start from index 1 if first segment is the doc title
        start = 1 if slides and slides[0]["is_doc_title"] else 0
        for seg in slides[start:]:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = seg["title"] or "Untitled"
            tf = slide.placeholders[1].text_frame
            tf.clear()
            for i, bullet in enumerate(seg["bullets"]):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.text = bullet
                p.font.size = Pt(18)

        buf = BytesIO()
        prs.save(buf)
        return buf.getvalue()

    @staticmethod
    def _dict_to_md(d: dict[str, Any]) -> str:
        from praxia.io.exporters.md_exporter import MarkdownExporter
        return MarkdownExporter._dict_to_md(d)

    @staticmethod
    def _segment(md: str) -> list[dict[str, Any]]:
        """Split markdown into slide segments."""
        slides: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for raw in md.splitlines():
            line = raw.rstrip()
            m1 = re.match(r"^#\s+(.*)$", line)
            m2 = re.match(r"^##\s+(.*)$", line)
            if m1:
                if current:
                    slides.append(current)
                current = {"title": m1.group(1), "bullets": [], "is_doc_title": True}
                continue
            if m2:
                if current:
                    slides.append(current)
                current = {"title": m2.group(1), "bullets": [], "is_doc_title": False}
                continue
            if current is None:
                current = {"title": "Overview", "bullets": [], "is_doc_title": False}
            stripped = line.lstrip()
            if re.match(r"^[-*+]\s+", stripped):
                current["bullets"].append(re.sub(r"^[-*+]\s+", "", stripped))
            elif re.match(r"^\d+\.\s+", stripped):
                current["bullets"].append(re.sub(r"^\d+\.\s+", "", stripped))
            elif stripped:
                current["bullets"].append(stripped)
        if current:
            slides.append(current)
        return slides or [{"title": "Praxia Output", "bullets": [], "is_doc_title": True}]
