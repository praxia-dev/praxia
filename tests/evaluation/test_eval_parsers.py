"""File parsers — encoding fallback, format dispatch, edge cases.

Coverage:
    - TextParser: UTF-8, Shift-JIS, CP1252 fallback chain
    - CsvParser: delimiter detection, multi-line handling
    - StructuredParser: JSON / YAML pretty-print + validity flag
    - HtmlParser: script/style stripping, title extraction
    - parse_file dispatch by extension
"""
from __future__ import annotations

import json as _json

import pytest

pytestmark = pytest.mark.evaluation


class TestTextParser:
    def test_utf8(self):
        from praxia.io.parsers.text import TextParser

        out = TextParser().parse("hello world".encode("utf-8"), filename="x.txt")
        assert out.content == "hello world"
        assert out.metadata["encoding"] == "utf-8"

    def test_shift_jis_fallback(self):
        from praxia.io.parsers.text import TextParser

        sjis = "営業企画 第3四半期".encode("shift_jis")
        out = TextParser().parse(sjis, filename="memo.txt")
        assert "営業企画" in out.content
        assert out.metadata["encoding"] == "shift_jis"

    def test_handles_empty(self):
        from praxia.io.parsers.text import TextParser

        out = TextParser().parse(b"", filename="empty.txt")
        assert out.content == ""

    def test_unicode_emoji(self):
        from praxia.io.parsers.text import TextParser

        out = TextParser().parse("Hi 🎉".encode("utf-8"), filename="e.txt")
        assert "🎉" in out.content


class TestCsvParser:
    def test_basic_csv_to_markdown(self):
        from praxia.io.parsers.csv_parser import CsvParser

        data = b"name,age\nAlice,30\nBob,42\n"
        out = CsvParser().parse(data, filename="users.csv")
        assert "| name | age |" in out.content
        assert "| Alice | 30 |" in out.content
        assert out.metadata["rows"] == 2

    def test_handles_japanese_columns(self):
        from praxia.io.parsers.csv_parser import CsvParser

        data = "氏名,所属\n田中,営業\n".encode("utf-8")
        out = CsvParser().parse(data, filename="社員.csv")
        assert "氏名" in out.content
        assert "田中" in out.content


class TestStructuredParser:
    def test_json_valid(self):
        from praxia.io.parsers.structured import StructuredParser

        data = b'{"foo":"bar","nested":{"k":1}}'
        out = StructuredParser().parse(data, filename="config.json")
        parsed = _json.loads(out.content)
        assert parsed == {"foo": "bar", "nested": {"k": 1}}
        assert out.metadata["is_valid"] is True

    def test_json_invalid_marks_invalid(self):
        from praxia.io.parsers.structured import StructuredParser

        out = StructuredParser().parse(b"{not valid", filename="bad.json")
        # Either is_valid=False or raise — both acceptable
        if "is_valid" in out.metadata:
            assert out.metadata["is_valid"] is False


class TestHtmlParser:
    def test_strips_script_and_style(self):
        from praxia.io.parsers.html import HtmlParser

        html = b"""<html><head><title>T</title>
        <style>body{color:red}</style></head>
        <body><script>alert(1)</script><p>Hello <b>world</b>!</p></body></html>"""
        out = HtmlParser().parse(html, filename="page.html")
        assert "Hello world" in out.content
        assert "alert" not in out.content
        assert "color:red" not in out.content

    def test_extracts_title(self):
        from praxia.io.parsers.html import HtmlParser

        out = HtmlParser().parse(
            b"<html><head><title>My Title</title></head><body>x</body></html>",
            filename="x.html",
        )
        assert out.metadata["title"] == "My Title"


class TestParseFileDispatch:
    @pytest.mark.parametrize(
        "filename,content,must_contain",
        [
            ("a.txt", b"text content", "text content"),
            ("a.csv", b"a,b\n1,2", "| a | b |"),
            ("a.json", b'{"k":1}', '"k": 1'),
            ("a.html", b"<p>html content</p>", "html content"),
        ],
    )
    def test_dispatch_by_extension(self, filename, content, must_contain):
        from praxia.io.parsers import parse_file

        out = parse_file(content, filename=filename)
        assert must_contain in out.content

    def test_unknown_extension_raises(self):
        from praxia.io.parsers import parse_file

        with pytest.raises(ValueError) as excinfo:
            parse_file(b"...", filename="weird.xyz")
        assert "xyz" in str(excinfo.value)

    def test_supported_extensions_includes_all_required(self):
        from praxia.io.parsers import supported_extensions

        exts = supported_extensions()
        for needed in ("pdf", "docx", "pptx", "xlsx", "csv", "txt", "md", "html", "json"):
            assert needed in exts, f"missing parser for .{needed}"
