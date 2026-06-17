"""PPTX exporter — converts Markdown / structured slide specs into a styled deck.

Two input shapes are supported, in priority order:

1. **Fenced structured-spec blocks** (recommended for the LLM):

   ```slide:cover
   title: Q3 Sales Review
   subtitle: ARR progression, customer feedback, roadmap
   kicker: 2026
   ```

   ```slide:section
   label: Customer Feedback
   number: 2
   ```

   ```slide:kpi
   title: Q3 highlights
   kpis:
     - {label: ARR added, value: $412k, delta: +$32k}
     - {label: NPS, value: 42, delta: +4 pts}
     - {label: Win rate, value: 22%, delta: -3 pts}
   ```

   ```slide:chart
   title: ARR added per quarter
   chart_type: bar
   labels: [Q1, Q2, Q3 target, Q3 actual]
   values: [285, 340, 380, 412]
   y_label: ARR added ($k)
   takeaways:
     - Q3 came in $32k above target
     - Self-service trial drove the lift
     - Q4 forecast holds at $440k
   ```

   ```slide:bullets
   title: Roadmap commitments
   bullets:
     - Ship Q4 onboarding revamp by 2026-10-15
     - Cut large-doc load latency to under 3s P95
     - Pilot SSO/Okta with the top 5 prospects
   ```

   Each fenced block routes to the matching helper in
   :mod:`praxia.io.slide_templates`. YAML or JSON body is accepted.

2. **Legacy Markdown** (backward compat):

   `# Title` becomes the cover slide; each `## Section` starts a
   ``bullets_slide``. This path still works when the LLM emits
   plain prose markdown, but loses the chart / KPI / section
   templates — slides will be uniform bullets_slide instances.

The result is always a python-pptx ``Presentation`` of 16:9 size
(``13.33 in x 7.5 in``), styled per :mod:`praxia.io.slide_style`.
"""
from __future__ import annotations

import json
import logging
import re
from io import BytesIO
from typing import Any

from praxia.io.slide_style import DEFAULT_STYLE, SlideStyle

_log = logging.getLogger(__name__)

_FENCE_RE = re.compile(
    r"```slide:(cover|section|kpi|chart|bullets)\s*\n(.*?)\n```",
    flags=re.DOTALL,
)


class PptxExporter:
    format = "pptx"
    extensions = ("pptx",)

    def __init__(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
        style: SlideStyle | None = None,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.author = author
        self.style = style or DEFAULT_STYLE

    def export(self, content: Any) -> bytes:
        try:
            from pptx import Presentation
            from pptx.util import Inches
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
        # Force 16:9 — the default 4:3 template feels dated and
        # makes the slide_templates layout coordinates wrong.
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)

        fenced = list(_FENCE_RE.finditer(content))
        if fenced:
            self._render_fenced(prs, content, fenced)
        else:
            self._render_legacy_markdown(prs, content)

        buf = BytesIO()
        prs.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Path 1 — fenced slide specs (new)
    # ------------------------------------------------------------------

    def _render_fenced(self, prs, content: str, matches: list[re.Match[str]]) -> None:
        """Walk the source in order, dispatching each fenced block to
        its template. Plain prose between fences is ignored — the
        caller is expected to put all renderable content inside
        fences when using this path."""
        from praxia.io.slide_templates import (
            bullets_slide,
            chart_slide,
            cover_slide,
            kpi_slide,
            section_slide,
        )
        any_cover = False
        for m in matches:
            kind = m.group(1)
            body = m.group(2).strip()
            spec = self._parse_spec(body)
            if spec is None:
                _log.warning(
                    "Skipping slide:%s — body did not parse as YAML/JSON: %r",
                    kind, body[:120],
                )
                continue
            try:
                if kind == "cover":
                    cover_slide(prs,
                                title=str(spec.get("title", self.title or "Praxia Output")),
                                subtitle=spec.get("subtitle") or self.subtitle,
                                kicker=spec.get("kicker"),
                                style=self.style)
                    any_cover = True
                elif kind == "section":
                    section_slide(prs,
                                  label=str(spec.get("label", "Section")),
                                  section_number=spec.get("number"),
                                  style=self.style)
                elif kind == "kpi":
                    kpi_slide(prs,
                              title=str(spec.get("title", "Highlights")),
                              kpis=list(spec.get("kpis") or []),
                              style=self.style)
                elif kind == "chart":
                    chart_slide(prs,
                                title=str(spec.get("title", "Chart")),
                                chart_type=str(spec.get("chart_type", "bar")),
                                labels=list(spec.get("labels") or []),
                                values=list(spec.get("values") or []),
                                series_names=spec.get("series_names"),
                                takeaways=list(spec.get("takeaways") or []),
                                y_label=spec.get("y_label"),
                                style=self.style)
                elif kind == "bullets":
                    bullets_slide(prs,
                                  title=str(spec.get("title", "Notes")),
                                  bullets=list(spec.get("bullets") or []),
                                  style=self.style)
            except Exception:
                _log.exception("Failed to render slide:%s — skipping", kind)
                continue
        if not any_cover:
            # If the LLM forgot a cover, prepend one so the deck
            # starts cleanly.
            from praxia.io.slide_templates import cover_slide
            cover_slide(prs,
                        title=self.title or "Praxia Output",
                        subtitle=self.subtitle,
                        style=self.style)
            # Move the synthesised cover to slide 1.
            xml_slides = prs.slides._sldIdLst  # type: ignore[attr-defined]
            slides = list(xml_slides)
            xml_slides.insert(0, slides[-1])
            xml_slides.remove(slides[-1])

    @staticmethod
    def _parse_spec(body: str) -> dict[str, Any] | None:
        """Accept YAML or JSON. We try JSON first (stricter, cheaper),
        then YAML (covers the LLM-friendly inline-list / scalar form)."""
        try:
            obj = json.loads(body)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
        try:
            import yaml  # type: ignore
            obj = yaml.safe_load(body)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Path 2 — legacy markdown (back-compat with pre-alpha39 callers)
    # ------------------------------------------------------------------

    def _render_legacy_markdown(self, prs, content: str) -> None:
        from praxia.io.slide_templates import bullets_slide, cover_slide

        slides = self._segment(content)

        # First segment becomes the cover if it's a doc title (# H1).
        if slides and slides[0]["is_doc_title"]:
            cover_slide(prs,
                        title=self.title or slides[0]["title"] or "Praxia Output",
                        subtitle=self.subtitle,
                        style=self.style)
            start = 1
        else:
            cover_slide(prs,
                        title=self.title or "Praxia Output",
                        subtitle=self.subtitle,
                        style=self.style)
            start = 0

        for seg in slides[start:]:
            bullets_slide(prs,
                          title=seg["title"] or "Untitled",
                          bullets=seg["bullets"],
                          style=self.style)

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
