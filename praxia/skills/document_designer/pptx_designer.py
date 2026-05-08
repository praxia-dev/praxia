"""PptxDesignerSkill — LLM writes python-pptx code, sandbox runs it, deck out."""
from __future__ import annotations

from typing import Any

from praxia.skills.skill import Skill, SkillManifest
from praxia.skills.document_designer.codegen import (
    CodegenBase,
    CodegenResult,
    _PPTX_TEMPLATE,
)
from praxia.skills.document_designer.theme import DocumentTheme, ThemeStore


class PptxDesignerSkill(CodegenBase, Skill):
    """Produce a design-rich .pptx from a free-text brief + theme.

    Unlike `OutputFormatSkill` (which converts existing markdown into a
    bare-bones deck via the structure-mapping exporter), this skill
    asks the LLM to AUTHOR python-pptx code that builds the deck —
    multi-column layouts, matrix slides, embedded matplotlib charts,
    custom theming, etc.
    """

    _TEMPLATE = _PPTX_TEMPLATE

    manifest = SkillManifest(
        name="pptx_designer",
        description=(
            "Author a design-rich PowerPoint deck from a brief. The LLM "
            "writes python-pptx code (sandboxed) that constructs slides "
            "with the user's chosen theme — colors, fonts, logo, footer, "
            "multi-column layouts."
        ),
        version="0.1.0",
        domain="utility",
        tags=["pptx", "presentation", "codegen", "design"],
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
        """Generate a .pptx for `brief`.

        Args:
            brief: free-text description of the deck (audience, sections,
                page count, tone, key data).
            theme: DocumentTheme to apply (colors / fonts / logo /
                footer). Defaults to a neutral theme.
            max_attempts: how many LLM-and-sandbox rounds to try before
                giving up. Each retry includes the previous failure's
                traceback in the prompt. Default 3.
            max_tokens: per-LLM-call output cap.
            timeout_s: sandbox wall-clock limit per attempt.
        """
        return self._codegen(
            brief, theme or DocumentTheme(),
            max_attempts=max_attempts, max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    # ---- Skill protocol -------------------------------------------------
    def run(self, user_input: str, **inputs: Any) -> bytes:
        """Skill-protocol entry point — returns the deck bytes.

        `inputs` may include:
            theme_name: str — theme to load from `.praxia/themes/`
            theme_dir:  str — override theme storage location
            max_attempts, max_tokens, timeout_s — passed through.
        """
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
