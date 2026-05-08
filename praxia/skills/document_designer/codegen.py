"""Shared meta-prompt + retry-loop machinery for the designer skills.

`CodegenBase` factors out the bits that are identical between Pptx and
Docx designers — assemble a meta-prompt with theme + few-shot examples,
ask the LLM, validate the AST, run the sandbox, on failure feed the
traceback back to the LLM (up to N times).
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from praxia.skills.document_designer.sandbox import (
    SandboxError,
    SandboxResult,
    SandboxTimeout,
    SandboxValidationError,
    run_in_sandbox,
)
from praxia.skills.document_designer.theme import DocumentTheme

if TYPE_CHECKING:
    from praxia.core.llm import LLM


# Block of "ground rules" common to pptx + docx codegen prompts.
_COMMON_RULES = textwrap.dedent("""
    Hard rules for the code you write:

    1. Only `import` from this exact allowlist:
       pptx, docx, matplotlib (with .pyplot, .figure, .patches, .colors, .cm),
       PIL (with .Image, .ImageDraw, .ImageFont, .ImageColor),
       numpy, math, statistics, random, fractions, decimal,
       io, base64, json, datetime, time, itertools, functools,
       collections, operator, copy, string, textwrap, re, uuid, hashlib,
       enum, dataclasses, typing.
       NO other imports. NO `os`, NO `subprocess`, NO `requests`, NO
       network, NO file I/O outside in-memory `io.BytesIO`.

    2. Never use `eval`, `exec`, `compile`, `__import__`, `globals()`,
       `locals()`, `vars()`, `breakpoint()`, `input()`, or any double-
       underscore introspection (`.__class__`, `.__bases__`, etc.).

    3. The runtime exposes one helper, `_emit(payload: bytes)`. Call it
       EXACTLY ONCE at the very end with the .pptx / .docx bytes.
       Example:
           buf = io.BytesIO()
           prs.save(buf)
           _emit(buf.getvalue())

    4. Wrap your whole program in a single top-level `def build():` and
       call `build()` at the end. This makes retries easier to diff.

    5. Output the code only — no prose, no markdown fences, no
       explanation. Start with `import ...` on line 1.

    6. Hard timeout in the sandbox is 30s. Keep code straightforward,
       no infinite loops, no large random datasets.
""").strip()


_PPTX_TEMPLATE = textwrap.dedent('''
    You are a senior presentation designer who writes Python code using
    `python-pptx`. Given a brief, produce a complete program that builds
    a polished slide deck.

    {rules}

    Theme to use (apply colors to backgrounds / fills, fonts to all
    titles & body text, place the logo on slide 1 and footer on every
    slide if specified):

    {theme_block}

    Available pptx layout idioms you can compose by hand:
      - title slide (large title, subtitle, logo bottom-right)
      - bullets slide (title + 3-6 bullets)
      - two-column slide (title + two text boxes side-by-side)
      - comparison slide (title + left/right boxes with header rows)
      - matrix slide (2x2 grid with quadrant labels)
      - image-full slide (one centered image, optional caption)
      - chart slide (matplotlib figure rendered to PNG, embedded)

    Brief from the user:

    {brief}

    Produce the python program now. Begin with the imports.
''').strip()


_DOCX_TEMPLATE = textwrap.dedent('''
    You are a senior document designer who writes Python code using
    `python-docx`. Given a brief, produce a complete program that builds
    a polished Word document.

    {rules}

    Theme to use (apply primary color to heading paragraphs, fonts to
    body and headings, footer_text to the page footer, logo at the top
    of page 1 if specified):

    {theme_block}

    Document elements you can compose:
      - cover page (title, subtitle, date, logo)
      - table of contents (Heading 1 / 2 anchors — python-docx doesn't
        auto-generate the TOC field, so build a fake one with hyperlinks
        OR just list the section titles as a styled bullet list)
      - heading hierarchy (Heading 1 = chapter, Heading 2 = section,
        Heading 3 = sub-section)
      - tables with header row styled in primary color
      - styled callout boxes (use a single-cell table with cell shading)
      - matplotlib chart embedded as an image
      - page footer with the theme footer_text and page number

    Brief from the user:

    {brief}

    Produce the python program now. Begin with the imports.
''').strip()


@dataclass
class CodegenAttempt:
    """Per-iteration record of what the LLM produced and how it ran."""
    iteration: int
    code: str
    success: bool
    error: str = ""
    duration_s: float = 0.0


@dataclass
class CodegenResult:
    """Final outcome of a designer-skill call."""
    bytes: bytes = b""
    attempts: list[CodegenAttempt] = field(default_factory=list)
    final_code: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.bytes)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


# ---------------------------------------------------------------------------
# Codegen base


class CodegenBase:
    """Mixin / helper holding the meta-prompt + retry-loop logic.

    Designer skill subclasses set `_TEMPLATE` to one of the constants
    above and call `_codegen(brief, theme, ...)` from their `design()`
    method.
    """

    _TEMPLATE: str = _PPTX_TEMPLATE  # overridden in subclasses

    def __init__(self, llm: "LLM | None" = None) -> None:
        from praxia.core.llm import LLM
        self.llm = llm or LLM()

    def _build_prompt(
        self,
        brief: str,
        theme: DocumentTheme,
    ) -> str:
        return self._TEMPLATE.format(
            rules=_COMMON_RULES,
            theme_block=theme.to_prompt_block(),
            brief=brief.strip(),
        )

    def _build_repair_prompt(
        self,
        brief: str,
        theme: DocumentTheme,
        last_code: str,
        error: str,
    ) -> str:
        """Prompt for the retry pass: include the last attempt + traceback."""
        return (
            self._build_prompt(brief, theme)
            + "\n\n# Previous attempt\n\n```python\n"
            + last_code.strip()
            + "\n```\n\n# Error from running the previous attempt\n\n"
            + error.strip()
            + "\n\nRewrite the program from scratch, fixing the error. "
            + "Output the new program only — no markdown fences, no commentary."
        )

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """LLMs often wrap code in ```python ... ``` despite our instructions.
        Strip the fence so the AST validator sees pure code."""
        s = text.strip()
        # Triple-backtick fence with optional language tag
        m = re.match(r"^```(?:python|py)?\s*\n(.*?)\n```\s*$", s, flags=re.DOTALL)
        if m:
            return m.group(1).strip()
        return s

    def _ask_llm_for_code(self, prompt: str, max_tokens: int) -> str:
        """One LLM round-trip; returns code with fences stripped."""
        resp = self.llm.complete(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return self._strip_code_fences(resp.text or "")

    def _codegen(
        self,
        brief: str,
        theme: DocumentTheme,
        *,
        max_attempts: int = 3,
        max_tokens: int = 16384,
        timeout_s: float = 30.0,
    ) -> CodegenResult:
        """Run the LLM → validate → sandbox → retry loop."""
        if not brief or not brief.strip():
            raise ValueError("`brief` must be a non-empty description.")

        prompt = self._build_prompt(brief, theme)
        last_code = ""
        last_error = ""
        attempts: list[CodegenAttempt] = []

        for i in range(1, max_attempts + 1):
            this_prompt = (
                prompt
                if i == 1
                else self._build_repair_prompt(brief, theme, last_code, last_error)
            )
            try:
                code = self._ask_llm_for_code(this_prompt, max_tokens)
            except Exception as e:  # noqa: BLE001 (we genuinely want any LLM error)
                attempts.append(CodegenAttempt(
                    iteration=i, code="", success=False,
                    error=f"LLM call failed: {e}",
                ))
                last_error = f"LLM call failed: {e}"
                continue

            last_code = code
            try:
                run: SandboxResult = run_in_sandbox(code, timeout_s=timeout_s)
                attempts.append(CodegenAttempt(
                    iteration=i, code=code, success=True,
                    duration_s=run.duration_s,
                ))
                return CodegenResult(
                    bytes=run.bytes, attempts=attempts, final_code=code,
                )
            except SandboxValidationError as e:
                last_error = (
                    f"AST validation rejected the code: {e}\n"
                    "Re-read the import allowlist and retry."
                )
            except SandboxTimeout as e:
                last_error = (
                    f"Sandbox timed out after {timeout_s}s: {e}\n"
                    "Simplify the code (no infinite loops, fewer matplotlib figures)."
                )
            except SandboxError as e:
                last_error = f"Sandbox error: {e}"
            except Exception as e:  # noqa: BLE001
                last_error = f"Unexpected error: {e}"

            attempts.append(CodegenAttempt(
                iteration=i, code=code, success=False, error=last_error,
            ))

        # Exhausted retries — surface the final error to the caller.
        raise RuntimeError(
            f"document designer failed after {max_attempts} attempts. "
            f"Last error: {last_error}"
        )
