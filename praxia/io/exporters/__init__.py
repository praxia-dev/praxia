"""Output exporters — turn agent / skill output into deliverables.

Skills produce text (typically Markdown). For end-user consumption, you
often want HTML (for the browser), PPTX (for stakeholder review), DOCX
(for reports), or just clean MD (for further editing).

Each exporter implements `Exporter`:

    class Exporter(Protocol):
        format: str
        extensions: tuple[str, ...]
        def export(self, content: str | dict, *, output_path: Path | None = None) -> bytes: ...

The output is always returned as `bytes` so the caller can stream it,
write it to disk, or push it through a connector. If `output_path` is
given the file is written there as well.

Registered via the same `praxia.extensions.Registry` primitive used for
connectors / parsers / backends, so third parties can add formats without
forking. Built-in formats:

    md      — passthrough or normalization (always available)
    html    — Markdown → HTML (built-in renderer, no extra deps)
    pptx    — slide-deck (auto-segments by ## headings) — requires `[office]`
    docx    — Word document — requires `[office]`
    pdf     — Word → PDF via reportlab — requires `[office]`
    json    — structured payload (echoes a dict)

Example:

    from praxia.io.exporters import export_as

    md_text = "# Quarterly Results\\n\\n## Revenue\\n- $1.2M ..."
    pptx_bytes = export_as(md_text, format="pptx")

The matching skill (`OutputFormatSkill`) chooses the format based on the
user's natural-language request ("作って ppt で", "as HTML", "PDF please").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from praxia.extensions import Registry, lazy
from praxia.io.exporters.base import Exporter, ExporterResult
from praxia.io.exporters.md_exporter import MarkdownExporter
from praxia.io.exporters.html_exporter import HtmlExporter
from praxia.io.exporters.json_exporter import JsonExporter

EXPORTERS: Registry[Exporter] = Registry(
    name="output exporter",
    entry_point_group="praxia.exporters",
)

EXPORTERS.register("md", MarkdownExporter)
EXPORTERS.register("markdown", MarkdownExporter)
EXPORTERS.register("html", HtmlExporter)
EXPORTERS.register("json", JsonExporter)
EXPORTERS.register("pptx", lazy("praxia.io.exporters.pptx_exporter:PptxExporter"))
EXPORTERS.register("docx", lazy("praxia.io.exporters.docx_exporter:DocxExporter"))


def export_as(
    content: Any,
    *,
    format: str,
    output_path: Path | str | None = None,
    **kwargs: Any,
) -> ExporterResult:
    """Convert `content` to `format` and (optionally) write to disk.

    Args:
        content: text (Markdown), or a structured payload (dict) if the
                 chosen exporter supports it.
        format:  "md" | "html" | "pptx" | "docx" | "json" | (custom)
        output_path: if provided, also write to this path.
        **kwargs: passed through to the exporter constructor (e.g.,
                  title, author, theme).

    Raises:
        ValueError: if format is unknown.
        ImportError: if the exporter requires an optional dep.
    """
    fmt = format.lower().lstrip(".")
    try:
        cls = EXPORTERS.get(fmt)
    except KeyError as e:
        raise ValueError(
            f"Unknown export format: {fmt!r}. Available: {', '.join(EXPORTERS.list())}"
        ) from e
    exporter = cls(**kwargs)
    payload = exporter.export(content)
    if output_path is not None:
        Path(output_path).write_bytes(payload)
    return ExporterResult(
        format=exporter.format,
        bytes=payload,
        suggested_extension=exporter.extensions[0],
        output_path=Path(output_path) if output_path else None,
    )


def supported_formats() -> list[str]:
    """All registered export format names."""
    return EXPORTERS.list()


__all__ = [
    "EXPORTERS",
    "Exporter",
    "ExporterResult",
    "export_as",
    "supported_formats",
    "MarkdownExporter",
    "HtmlExporter",
    "JsonExporter",
]
