"""Tests for the document_designer skill module — sandbox + theme.

These tests exercise the sandbox executor + theme storage WITHOUT
hitting an LLM. The codegen retry-loop part is covered by integration
tests gated on a live API key.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# AST validator


def test_ast_blocks_os_import():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError, match="forbidden import"):
        validate_code("import os")


def test_ast_blocks_subprocess_import():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError):
        validate_code("import subprocess")


def test_ast_blocks_eval():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError, match="eval"):
        validate_code("eval('1+1')")


def test_ast_blocks_exec():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError, match="exec"):
        validate_code("exec('x=1')")


def test_ast_blocks_dunder_escape():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError, match="forbidden attribute"):
        validate_code("().__class__.__bases__")


def test_ast_allows_pptx_and_io():
    from praxia.skills.document_designer import validate_code

    # Should not raise
    validate_code("import pptx\nimport io\nprint('ok')")


def test_ast_allows_from_import():
    from praxia.skills.document_designer import validate_code

    validate_code("from pptx.util import Pt, Inches")
    validate_code("from io import BytesIO")


def test_ast_blocks_from_os_import():
    from praxia.skills.document_designer import validate_code, SandboxValidationError

    with pytest.raises(SandboxValidationError, match="forbidden"):
        validate_code("from os import path")


# ---------------------------------------------------------------------------
# Sandbox runner (real subprocess; fast)


def test_sandbox_emits_payload_back():
    from praxia.skills.document_designer import run_in_sandbox

    code = (
        "def build():\n"
        "    _emit(b'hello sandbox')\n"
        "build()\n"
    )
    r = run_in_sandbox(code, timeout_s=10)
    assert r.ok
    assert r.bytes == b"hello sandbox"
    assert r.returncode == 0


def test_sandbox_rejects_disallowed_import_before_running():
    from praxia.skills.document_designer import run_in_sandbox, SandboxValidationError

    with pytest.raises(SandboxValidationError):
        run_in_sandbox("import os\n_emit(b'x')\n", timeout_s=10)


def test_sandbox_propagates_runtime_error():
    from praxia.skills.document_designer import run_in_sandbox, SandboxError

    code = "raise ValueError('boom')\n"
    with pytest.raises(SandboxError, match="exited with code"):
        run_in_sandbox(code, timeout_s=10)


def test_sandbox_missing_emit_raises():
    from praxia.skills.document_designer import run_in_sandbox, SandboxError

    code = "x = 1\n"  # no _emit call
    with pytest.raises(SandboxError, match="without emitting"):
        run_in_sandbox(code, timeout_s=10)


# ---------------------------------------------------------------------------
# DocumentTheme + ThemeStore


def test_theme_defaults_validate():
    from praxia.skills.document_designer import DocumentTheme

    t = DocumentTheme()
    assert t.validate() == []
    block = t.to_prompt_block()
    assert "Colors:" in block
    assert "Fonts:" in block


def test_theme_invalid_color_caught():
    from praxia.skills.document_designer import DocumentTheme

    t = DocumentTheme(colors={
        "primary": "not-a-hex",
        "accent": "#00ff00",
        "background": "#ffffff",
        "muted": "#888888",
        "text": "#000000",
    })
    errors = t.validate()
    assert any("primary" in e for e in errors)


def test_theme_store_save_load_delete():
    from praxia.skills.document_designer import DocumentTheme, ThemeStore

    with tempfile.TemporaryDirectory() as d:
        store = ThemeStore(base_dir=d)
        assert store.list_names() == []
        theme = DocumentTheme(
            name="test_corp",
            footer_text="Test footer",
        )
        store.save(theme)
        assert "test_corp" in store.list_names()

        loaded = store.load("test_corp")
        assert loaded.name == "test_corp"
        assert loaded.footer_text == "Test footer"

        assert store.delete("test_corp")
        assert store.list_names() == []


def test_theme_store_attaches_logo_bytes():
    from praxia.skills.document_designer import DocumentTheme, ThemeStore

    with tempfile.TemporaryDirectory() as d:
        store = ThemeStore(base_dir=d)
        theme = DocumentTheme(name="with_logo")
        # 1x1 transparent PNG
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
            b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc"
            b"\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        store.save(theme, logo_bytes=png, logo_filename="logo.png")
        loaded = store.load("with_logo")
        assert loaded.logo_path is not None
        assert Path(loaded.logo_path).is_file()
        assert Path(loaded.logo_path).suffix == ".png"


def test_theme_store_rejects_invalid_name():
    from praxia.skills.document_designer import DocumentTheme, ThemeStore

    with tempfile.TemporaryDirectory() as d:
        store = ThemeStore(base_dir=d)
        theme = DocumentTheme(name="../escape/attempt")
        with pytest.raises(ValueError, match="invalid theme"):
            store.save(theme)


# ---------------------------------------------------------------------------
# Skill registration


def test_designer_skills_registered():
    from praxia.skills import (
        DocxDesignerSkill,
        PptxDesignerSkill,
        SKILLS,
    )

    assert SKILLS.has("pptx_designer")
    assert SKILLS.has("docx_designer")
    assert SKILLS.get("pptx_designer") is PptxDesignerSkill
    assert SKILLS.get("docx_designer") is DocxDesignerSkill
