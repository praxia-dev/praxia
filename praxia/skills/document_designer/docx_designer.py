"""DocxDesignerSkill — LLM writes python-docx code, sandbox runs it, doc out."""
from __future__ import annotations

from typing import Any

from praxia.skills.skill import Skill, SkillManifest
from praxia.skills.document_designer.codegen import (
    CodegenBase,
    CodegenResult,
    _DOCX_TEMPLATE,
)
from praxia.skills.document_designer.theme import DocumentTheme, ThemeStore


class DocxDesignerSkill(CodegenBase, Skill):
    """Produce a design-rich .docx from a free-text brief + theme.

    Mirror of PptxDesignerSkill but for Word documents. The LLM authors
    python-docx code (sandboxed) that constructs the document with the
    chosen theme — heading hierarchy, page footer, branded colors,
    embedded charts.
    """

    _TEMPLATE = _DOCX_TEMPLATE

    manifest = SkillManifest(
        name="docx_designer",
        description=(
            "Author a design-rich Word document from a brief. The LLM "
            "writes python-docx code (sandboxed) that constructs the doc "
            "with the user's chosen theme — colors, fonts, logo, footer, "
            "tables, callouts, embedded charts."
        ),
        version="0.1.0",
        domain="utility",
        tags=["docx", "word", "codegen", "design"],
    )

    def design(
        self,
        brief: str,
        *,
        theme: DocumentTheme | None = None,
        max_attempts: int = 3,
        max_tokens: int = 16384,
        timeout_s: float = 30.0,
    ) -> CodegenResult:
        """Generate a .docx for `brief`. See PptxDesignerSkill.design()."""
        return self._codegen(
            brief, theme or DocumentTheme(),
            max_attempts=max_attempts, max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    def run(self, user_input: str, **inputs: Any) -> bytes:
        theme: DocumentTheme | None = inputs.get("theme")
        if theme is None and inputs.get("theme_name"):
            store = ThemeStore(
                base_dir=inputs.get("theme_dir") or ".praxia/themes",
            )
            theme = store.load(str(inputs["theme_name"]))
        result = self.design(
            user_input,
            theme=theme,
            max_attempts=int(inputs.get("max_attempts", 3)),
            max_tokens=int(inputs.get("max_tokens", 16384)),
            timeout_s=float(inputs.get("timeout_s", 30.0)),
        )
        return result.bytes
