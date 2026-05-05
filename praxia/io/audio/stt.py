"""Speech-to-text (STT) for voice input.

Provider-agnostic facade. Auto-picks based on env vars:
    1. OPENAI_API_KEY → OpenAI Whisper API (recommended; ~$0.006/min)
    2. (future) ANTHROPIC_API_KEY when Claude voice is GA
    3. Fallback: local whisper.cpp (no internet, slower)
"""
from __future__ import annotations

import io
import os
from typing import Any


class STT:
    """Speech-to-text — transcribes audio bytes to plain text."""

    def __init__(self, *, provider: str = "auto", **kwargs: Any) -> None:
        self.provider = provider if provider != "auto" else self._auto_pick()
        self._kwargs = kwargs

    @staticmethod
    def _auto_pick() -> str:
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        # Fallback: local
        return "whisper_cpp"

    def transcribe(
        self,
        audio: bytes | io.BytesIO,
        *,
        filename: str = "audio.wav",
        language: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Transcribe `audio` bytes (WAV / MP3 / M4A) to text.

        Args:
            audio:    raw audio bytes or a file-like object
            filename: used for content-type detection
            language: optional ISO-639 hint, e.g. "ja" or "en". Auto by default.
        """
        if self.provider == "openai":
            return self._transcribe_openai(audio, filename, language=language)
        if self.provider == "whisper_cpp":
            return self._transcribe_whisper_cpp(audio, filename, language=language)
        raise ValueError(f"Unsupported STT provider: {self.provider}")

    # --- OpenAI Whisper API -----------------------------------------------

    def _transcribe_openai(
        self,
        audio: bytes | io.BytesIO,
        filename: str,
        *,
        language: str | None,
    ) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "OpenAI Whisper STT requires `openai`. Install with:\n"
                '  pip install "praxia[audio]"'
            ) from e

        client = OpenAI()
        if isinstance(audio, bytes):
            buf = io.BytesIO(audio)
            buf.name = filename
        else:
            buf = audio
            if not getattr(buf, "name", None):
                buf.name = filename

        request_kwargs: dict[str, Any] = {
            "model": self._kwargs.get("model", "whisper-1"),
            "file": buf,
        }
        if language:
            request_kwargs["language"] = language

        response = client.audio.transcriptions.create(**request_kwargs)
        return response.text

    # --- Local whisper.cpp ------------------------------------------------

    def _transcribe_whisper_cpp(
        self,
        audio: bytes | io.BytesIO,
        filename: str,
        *,
        language: str | None,
    ) -> str:  # pragma: no cover — exercised only when whisper-cpp present
        try:
            import whisper
        except ImportError as e:
            raise ImportError(
                "Local whisper requires `openai-whisper`. Install with:\n"
                '  pip install "praxia[audio-local]"'
            ) from e

        # Save bytes to a temp file because whisper expects a path
        import tempfile

        suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio if isinstance(audio, bytes) else audio.getvalue())
            tmp_path = tmp.name

        model = whisper.load_model(self._kwargs.get("model", "base"))
        result = model.transcribe(tmp_path, language=language)
        return result.get("text", "")


# Convenience alias
SpeechToText = STT
