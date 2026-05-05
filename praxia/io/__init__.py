"""File parsers, audio I/O, and output exporters for Praxia.

Three halves:

* `praxia.io.parsers` — Convert uploaded files (PDF, Word, PowerPoint,
  Excel, CSV, plain text) into LLM-ready text.
* `praxia.io.audio` — Speech-to-text (STT) for voice input and
  text-to-speech (TTS) for voice output.
* `praxia.io.exporters` — Convert agent / skill output (Markdown by
  default) into deliverables (HTML, PPTX, DOCX, JSON).

All three use the same pluggable `praxia.extensions.Registry` so adding
new formats is drop-in.
"""
from praxia.io.parsers import PARSERS, ParsedFile, parse_file
from praxia.io.audio import STT, TTS
from praxia.io.exporters import EXPORTERS, ExporterResult, export_as, supported_formats

__all__ = [
    "PARSERS",
    "ParsedFile",
    "parse_file",
    "STT",
    "TTS",
    "EXPORTERS",
    "ExporterResult",
    "export_as",
    "supported_formats",
]
