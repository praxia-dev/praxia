"""Document designer skills — LLM-authored python-pptx / python-docx code,
executed in a sandbox to produce design-rich .pptx / .docx files.

Pipeline:
    user brief → LLM generates Python code → AST allowlist check
    → subprocess sandbox (timeout + memory limit on POSIX) → bytes
    → on error, feed traceback back to LLM and retry (up to N times)

Inspired by Anthropic's Claude Code Skills approach: rather than mapping
markdown to a rigid template, let the LLM compose the document
programmatically. The resulting deck / doc can use multi-column layouts,
matrix slides, embedded matplotlib charts, custom theming — anything
expressible in python-pptx / python-docx.
"""
from __future__ import annotations

from praxia.skills.document_designer.theme import DocumentTheme, ThemeStore
from praxia.skills.document_designer.sandbox import (
    SandboxResult,
    SandboxError,
    SandboxTimeout,
    SandboxValidationError,
    run_in_sandbox,
    validate_code,
)
from praxia.skills.document_designer.codegen import (
    CodegenAttempt,
    CodegenBase,
    CodegenResult,
)
from praxia.skills.document_designer.pptx_designer import PptxDesignerSkill
from praxia.skills.document_designer.docx_designer import DocxDesignerSkill

__all__ = [
    "DocumentTheme",
    "ThemeStore",
    "SandboxResult",
    "SandboxError",
    "SandboxTimeout",
    "SandboxValidationError",
    "run_in_sandbox",
    "validate_code",
    "CodegenAttempt",
    "CodegenBase",
    "CodegenResult",
    "PptxDesignerSkill",
    "DocxDesignerSkill",
]
