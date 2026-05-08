"""File-format parsers — pluggable via the same Registry mechanism as
connectors / backends. Adding a new format is a drop-in plugin.

Built-in formats:

| Extension(s)    | Parser              | Optional dependency  |
|-----------------|---------------------|----------------------|
| .txt .md .rst   | TextParser          | (none)               |
| .csv .tsv       | CsvParser           | (none, stdlib)       |
| .json .yaml .yml| StructuredParser    | pyyaml (already core)|
| .py .ts .js etc.| TextParser          | (none)               |
| .html .xml      | HtmlParser          | (none, stdlib)       |
| .pdf            | PdfParser           | pypdf                |
| .docx           | DocxParser          | python-docx          |
| .pptx           | PptxParser          | python-pptx          |
| .xlsx .xlsm     | XlsxParser          | openpyxl             |

Third-party parsers register via entry-points:

    [project.entry-points."praxia.parsers"]
    rtf = "my_pkg.rtf:RtfParser"

Then `parse_file("notes.rtf")` will auto-dispatch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO

from praxia.extensions import Registry, lazy
from praxia.io.parsers.base import FileParser, ParsedFile

PARSERS: Registry[FileParser] = Registry(
    name="file parser",
    entry_point_group="praxia.parsers",
)

# Built-in registrations — keyed by lowercase extension WITHOUT the dot
PARSERS.register("txt", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("md", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("rst", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("py", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("ts", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("js", lazy("praxia.io.parsers.text:TextParser"))
PARSERS.register("html", lazy("praxia.io.parsers.html:HtmlParser"))
PARSERS.register("xml", lazy("praxia.io.parsers.html:HtmlParser"))
PARSERS.register("csv", lazy("praxia.io.parsers.csv_parser:CsvParser"))
PARSERS.register("tsv", lazy("praxia.io.parsers.csv_parser:CsvParser"))
PARSERS.register("json", lazy("praxia.io.parsers.structured:StructuredParser"))
PARSERS.register("yaml", lazy("praxia.io.parsers.structured:StructuredParser"))
PARSERS.register("yml", lazy("praxia.io.parsers.structured:StructuredParser"))

PARSERS.register("pdf", lazy("praxia.io.parsers.pdf:PdfParser"))
PARSERS.register("docx", lazy("praxia.io.parsers.docx_parser:DocxParser"))
PARSERS.register("pptx", lazy("praxia.io.parsers.pptx_parser:PptxParser"))
PARSERS.register("xlsx", lazy("praxia.io.parsers.xlsx_parser:XlsxParser"))
PARSERS.register("xlsm", lazy("praxia.io.parsers.xlsx_parser:XlsxParser"))

# Image formats — content is a placeholder, metadata["image"] holds the
# base64 + mime so vision-capable agents can pick them up.
PARSERS.register("png", lazy("praxia.io.parsers.image_parser:ImageParser"))
PARSERS.register("jpg", lazy("praxia.io.parsers.image_parser:ImageParser"))
PARSERS.register("jpeg", lazy("praxia.io.parsers.image_parser:ImageParser"))
PARSERS.register("gif", lazy("praxia.io.parsers.image_parser:ImageParser"))
PARSERS.register("webp", lazy("praxia.io.parsers.image_parser:ImageParser"))


def parse_file(
    source: str | Path | BinaryIO,
    *,
    filename: str | None = None,
    **kwargs: Any,
) -> ParsedFile:
    """Auto-dispatch to the right parser based on extension.

    Args:
        source:   path-like or open binary file-like object
        filename: required when `source` is a stream (used to pick parser)
        **kwargs: forwarded to the parser

    Raises:
        ValueError: when no parser matches the extension
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        ext = path.suffix.lower().lstrip(".")
        with path.open("rb") as f:
            data = f.read()
        name = path.name
    else:
        if not filename:
            raise ValueError(
                "filename is required when source is a stream "
                "(used to determine the parser by extension)"
            )
        ext = Path(filename).suffix.lower().lstrip(".")
        # Streams might already be at end if read; reset where possible
        if hasattr(source, "seek"):
            try:
                source.seek(0)
            except Exception:
                pass
        data = source.read() if hasattr(source, "read") else source
        name = filename

    if not PARSERS.has(ext):
        raise ValueError(
            f"No parser registered for extension {ext!r}. "
            f"Available: {sorted(PARSERS.list())}"
        )
    parser_cls = PARSERS.get(ext)
    parser = parser_cls()
    return parser.parse(data, filename=name, **kwargs)


def supported_extensions() -> list[str]:
    """List all registered extensions (built-in + entry-point)."""
    return sorted(PARSERS.list())


__all__ = ["PARSERS", "FileParser", "ParsedFile", "parse_file", "supported_extensions"]
