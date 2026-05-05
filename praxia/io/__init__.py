"""File parsers and audio I/O for Praxia.

Two halves:

* `praxia.io.parsers` — Convert uploaded files (PDF, Word, PowerPoint,
  Excel, CSV, plain text) into LLM-ready text. Uses the same pluggable
  Registry pattern as connectors / backends so adding new formats is
  drop-in.
* `praxia.io.audio` — Speech-to-text (STT) for voice input and
  text-to-speech (TTS) for voice output. Provider-agnostic.
"""
from praxia.io.parsers import PARSERS, ParsedFile, parse_file
from praxia.io.audio import STT, TTS

__all__ = ["PARSERS", "ParsedFile", "parse_file", "STT", "TTS"]
