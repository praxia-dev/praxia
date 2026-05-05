"""OutputFormatSkill — pick the optimal output format from a user request.

Most skills produce Markdown. End users often want their output in a
specific format ("PowerPoint で出して", "as HTML", "give me a Word doc").
This skill:

    1. Parses the user's request → infers a target format.
    2. Calls a producer skill (or runs a prompt) → gets Markdown content.
    3. Hands the Markdown to the matching `praxia.io.exporters` exporter.

It does NOT replace business skills — it composes with them.

Example:

    from praxia.skills.output_format import OutputFormatSkill
    from praxia.skills.business import InvestmentSkill

    fmt = OutputFormatSkill()
    md = InvestmentSkill().run("Q3 review of Acme Corp")
    result = fmt.deliver(md, user_request="このレポートをパワポで")
    # result.format == "pptx"
    # result.bytes  → write to disk or stream to user
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from praxia.io.exporters import ExporterResult, export_as
from praxia.skills.skill import Skill, SkillManifest


@dataclass
class FormatRequest:
    """Result of parsing a user's natural-language format request."""

    format: str
    confidence: float
    reason: str


# Heuristics: keyword → canonical format. English + Japanese.
_FORMAT_KEYWORDS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\b(pptx|powerpoint|slides?|deck)\b|スライド|パワポ|プレゼン", re.IGNORECASE),
     "pptx", "PowerPoint / slide-deck request"),
    (re.compile(r"\b(docx|word|doc(?:ument)?)\b|ワード|文書|ドキュメント", re.IGNORECASE),
     "docx", "Word document request"),
    (re.compile(r"\b(html|web)\b|ブラウザ", re.IGNORECASE),
     "html", "HTML request"),
    (re.compile(r"\b(json|api)\b", re.IGNORECASE),
     "json", "JSON / API request"),
    (re.compile(r"\b(md|markdown)\b|マークダウン", re.IGNORECASE),
     "md", "Markdown request"),
    (re.compile(r"\b(pdf)\b", re.IGNORECASE),
     "pdf", "PDF request (note: PDF is rendered via DOCX → reportlab if available)"),
]


class OutputFormatSkill(Skill):
    """Selects an output format from natural-language hints."""

    manifest = SkillManifest(
        name="output_formatter",
        description="Detect requested output format and render skill output accordingly.",
        domain="utility",
        tags=["formatting", "delivery"],
    )
    system_prompt = (
        "You are an output-format detector. Given a user's request, identify "
        "which deliverable format they want (md / html / pptx / docx / json). "
        "When ambiguous, default to md."
    )

    def detect(self, user_request: str, *, default: str = "md") -> FormatRequest:
        """Parse the user's request and pick a target format.

        Pure heuristic; does not call the LLM. The Skill's `system_prompt`
        is used only by `detect_with_llm` (slower but smarter).
        """
        text = user_request or ""
        for pattern, fmt, reason in _FORMAT_KEYWORDS:
            if pattern.search(text):
                return FormatRequest(format=fmt, confidence=0.85, reason=reason)
        return FormatRequest(
            format=default,
            confidence=0.4,
            reason="no explicit format keyword found — using default",
        )

    def detect_with_llm(self, user_request: str, *, default: str = "md") -> FormatRequest:
        """LLM-judged variant for hard cases."""
        first = self.detect(user_request, default=default)
        if first.confidence >= 0.85:
            return first
        prompt = (
            "Choose ONE output format the user wants. Reply with only the "
            "format name (md / html / pptx / docx / json). If unclear, reply 'md'.\n\n"
            f"User request: {user_request}"
        )
        try:
            resp = self.llm.complete([{"role": "user", "content": prompt}])
            chosen = resp.text.strip().lower().split()[0] if resp.text.strip() else default
            chosen = re.sub(r"[^a-z]", "", chosen)
            if chosen not in {"md", "html", "pptx", "docx", "json", "pdf"}:
                chosen = default
            return FormatRequest(format=chosen, confidence=0.9, reason="LLM-classified")
        except Exception as e:
            return FormatRequest(
                format=default, confidence=0.3, reason=f"LLM failed: {e}"
            )

    def deliver(
        self,
        content: Any,
        *,
        user_request: str = "",
        format: str | None = None,
        output_path: str | None = None,
        **exporter_kwargs: Any,
    ) -> ExporterResult:
        """Render `content` to a deliverable.

        Args:
            content:       Markdown text (or dict) produced by another skill.
            user_request:  natural-language hint (used if `format` is None).
            format:        explicit format override; skips detection.
            output_path:   write the bytes to this path as well as returning.
            **exporter_kwargs: passed to the chosen exporter (title, css, etc.).
        """
        if format is None:
            format = self.detect(user_request).format
        return export_as(
            content, format=format, output_path=output_path, **exporter_kwargs
        )
