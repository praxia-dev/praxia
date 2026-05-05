"""Output exporters — every format under multiple inputs.

Coverage:
    - Markdown passthrough + frontmatter combinations
    - HTML rendering: headings 1-6, lists, code blocks, links, bold, italic
    - HTML XSS sanitization (script tag stripped)
    - JSON: dict input + string input
    - PPTX / DOCX: import-or-skip (optional dep)
    - Format inference via OutputFormatSkill (English + Japanese)
"""
from __future__ import annotations

import importlib.util
import json as _json

import pytest

pytestmark = pytest.mark.evaluation


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


# --- MarkdownExporter -------------------------------------------------------

class TestMarkdownExporter:
    def test_passthrough(self):
        from praxia.io.exporters import export_as

        text = "# Title\n\nbody"
        result = export_as(text, format="md")
        assert result.bytes.decode("utf-8") == text

    def test_with_frontmatter_adds_yaml_block(self):
        from praxia.io.exporters import export_as

        result = export_as(
            "body",
            format="md",
            title="My Doc",
            author="Alice",
            frontmatter={"tags": "test"},
        )
        text = result.bytes.decode("utf-8")
        assert text.startswith("---\n")
        assert "title: My Doc" in text
        assert "author: Alice" in text
        assert "tags: test" in text
        assert text.endswith("body".rstrip("\n") + "\n") or "body" in text

    def test_dict_input_renders_sections(self):
        from praxia.io.exporters import export_as

        d = {
            "title": "Q3",
            "sections": [
                {"heading": "Revenue", "body": "$1.2M"},
                {"heading": "Risks", "body": "FX exposure"},
            ],
        }
        result = export_as(d, format="md")
        text = result.bytes.decode("utf-8")
        assert "# Q3" in text
        assert "## Revenue" in text
        assert "$1.2M" in text


# --- HtmlExporter -----------------------------------------------------------

class TestHtmlExporter:
    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_heading_levels(self, level):
        from praxia.io.exporters import export_as

        md = "#" * level + " H"
        html = export_as(md, format="html").bytes.decode("utf-8")
        assert f"<h{level}>H</h{level}>" in html

    def test_unordered_list(self):
        from praxia.io.exporters import export_as

        md = "- a\n- b\n- c"
        html = export_as(md, format="html").bytes.decode("utf-8")
        assert "<ul>" in html
        assert "<li>a</li>" in html
        assert "<li>c</li>" in html

    def test_ordered_list(self):
        from praxia.io.exporters import export_as

        md = "1. first\n2. second"
        html = export_as(md, format="html").bytes.decode("utf-8")
        assert "<ol>" in html
        assert "<li>first</li>" in html

    def test_inline_code(self):
        from praxia.io.exporters import export_as

        html = export_as("use `foo()` here", format="html").bytes.decode("utf-8")
        assert "<code>foo()</code>" in html

    def test_fenced_code_block(self):
        from praxia.io.exporters import export_as

        md = "```python\nprint('hi')\n```"
        html = export_as(md, format="html").bytes.decode("utf-8")
        assert "<pre><code" in html
        assert "lang-python" in html
        assert "print" in html

    def test_bold_and_italic(self):
        from praxia.io.exporters import export_as

        html = export_as("**bold** and *italic*", format="html").bytes.decode("utf-8")
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html

    def test_links(self):
        from praxia.io.exporters import export_as

        html = export_as("[Praxia](https://praxia.dev)", format="html").bytes.decode(
            "utf-8"
        )
        assert 'href="https://praxia.dev"' in html
        assert ">Praxia</a>" in html

    def test_xss_script_tag_escaped(self):
        from praxia.io.exporters import export_as

        md = "<script>alert(1)</script>"
        html = export_as(md, format="html").bytes.decode("utf-8")
        # The literal <script> tag must not appear unescaped
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_blockquote(self):
        from praxia.io.exporters import export_as

        html = export_as("> quoted text", format="html").bytes.decode("utf-8")
        assert "<blockquote>quoted text</blockquote>" in html

    def test_wrap_in_document_default(self):
        from praxia.io.exporters import export_as

        html = export_as("# x", format="html", title="MyTitle").bytes.decode("utf-8")
        assert "<!DOCTYPE html>" in html
        assert "<title>MyTitle</title>" in html
        assert "<style>" in html

    def test_no_wrap_returns_fragment(self):
        from praxia.io.exporters import export_as

        html = export_as(
            "# x", format="html", wrap_in_document=False
        ).bytes.decode("utf-8")
        assert "<!DOCTYPE" not in html
        assert "<h1>x</h1>" in html

    def test_japanese_content_preserved(self):
        from praxia.io.exporters import export_as

        html = export_as("# 営業企画", format="html").bytes.decode("utf-8")
        assert "営業企画" in html


# --- JsonExporter -----------------------------------------------------------

class TestJsonExporter:
    def test_dict_input(self):
        from praxia.io.exporters import export_as

        result = export_as({"foo": "bar", "n": 42}, format="json")
        parsed = _json.loads(result.bytes)
        assert parsed == {"foo": "bar", "n": 42}

    def test_string_input_wraps(self):
        from praxia.io.exporters import export_as

        result = export_as("hello", format="json")
        parsed = _json.loads(result.bytes)
        assert parsed == {"text": "hello"}

    def test_japanese_not_ascii_escaped_by_default(self):
        from praxia.io.exporters import export_as

        result = export_as({"text": "日本語"}, format="json")
        text = result.bytes.decode("utf-8")
        assert "日本語" in text
        # Not 日本語
        assert "\\u65e5" not in text


# --- PPTX (optional dep) ----------------------------------------------------

@pytest.mark.skipif(not _has("pptx"), reason="python-pptx not installed")
class TestPptxExporter:
    def test_export_returns_zip_bytes(self):
        from praxia.io.exporters import export_as

        md = "# Title\n\n## S1\n- a\n- b\n\n## S2\n- c"
        result = export_as(md, format="pptx", title="T")
        # PPTX = ZIP file; first 2 bytes = "PK"
        assert result.bytes[:2] == b"PK"
        assert result.size > 1000  # not empty

    def test_segments_into_slides(self):
        from io import BytesIO
        from pptx import Presentation
        from praxia.io.exporters import export_as

        md = "# Doc Title\n\n## Slide A\n- a1\n\n## Slide B\n- b1"
        result = export_as(md, format="pptx")
        prs = Presentation(BytesIO(result.bytes))
        # 1 title slide + 2 content slides
        assert len(prs.slides) == 3


# --- DOCX (optional dep) ----------------------------------------------------

@pytest.mark.skipif(not _has("docx"), reason="python-docx not installed")
class TestDocxExporter:
    def test_export_returns_zip_bytes(self):
        from praxia.io.exporters import export_as

        md = "# Title\n\n## Section\n\nbody text"
        result = export_as(md, format="docx", title="T")
        assert result.bytes[:2] == b"PK"
        assert result.size > 1000


# --- Format inference (OutputFormatSkill) -----------------------------------

class TestOutputFormatSkill:
    @pytest.mark.parametrize(
        "request_text,expected_format",
        [
            # English
            ("PowerPoint please", "pptx"),
            ("can you give me slides?", "pptx"),
            ("a deck of 5 slides", "pptx"),
            ("Word doc please", "docx"),
            ("HTML for the browser", "html"),
            ("just markdown", "md"),
            ("JSON for my API", "json"),
            ("PDF format", "pdf"),
            # Japanese
            ("レポートをパワポで", "pptx"),
            ("スライドにして", "pptx"),
            ("プレゼン用に作って", "pptx"),
            ("ワード文書で", "docx"),
            ("ドキュメント形式", "docx"),
            ("ブラウザで見たい", "html"),
            ("マークダウンで", "md"),
            # Default fallback
            ("just give me something", "md"),
        ],
    )
    def test_detect_inference(self, request_text, expected_format):
        from praxia.skills.output_format import OutputFormatSkill

        result = OutputFormatSkill().detect(request_text)
        assert result.format == expected_format, (
            f"{request_text!r} → expected {expected_format}, got {result.format}"
        )

    def test_deliver_returns_bytes_and_metadata(self):
        from praxia.skills.output_format import OutputFormatSkill

        fs = OutputFormatSkill()
        result = fs.deliver("# H\n\nbody", user_request="HTML")
        assert result.format == "html"
        assert b"<h1>H</h1>" in result.bytes
        assert result.size > 0


# --- Registry / extension --------------------------------------------------

class TestExporterRegistry:
    def test_supported_formats_include_builtins(self):
        from praxia.io.exporters import supported_formats

        formats = supported_formats()
        for needed in ("md", "markdown", "html", "json", "pptx", "docx"):
            assert needed in formats

    def test_unknown_format_raises(self):
        from praxia.io.exporters import export_as

        with pytest.raises(ValueError) as excinfo:
            export_as("x", format="weirdfmt")
        assert "weirdfmt" in str(excinfo.value)

    def test_output_path_writes_file(self, tmp_storage):
        from praxia.io.exporters import export_as

        out = tmp_storage / "result.html"
        result = export_as("# x", format="html", output_path=out)
        assert out.exists()
        assert out.read_bytes() == result.bytes
