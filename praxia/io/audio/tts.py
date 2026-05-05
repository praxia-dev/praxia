"""Text-to-speech (TTS) for voice output.

Provider-agnostic facade. Auto-picks based on env vars:
    1. OPENAI_API_KEY → OpenAI TTS (recommended; 6 voices, ~$15/1M chars)
    2. ELEVENLABS_API_KEY → ElevenLabs (premium, voice cloning)
    3. (future) Local Piper TTS (no key, on-prem)
"""
from __future__ import annotations

import os
from typing import Any, Literal

VoiceFormat = Literal["mp3", "wav", "opus", "aac", "flac", "pcm"]


class TTS:
    """Text-to-speech — converts text to audio bytes."""

    def __init__(self, *, provider: str = "auto", **kwargs: Any) -> None:
        self.provider = provider if provider != "auto" else self._auto_pick()
        self._kwargs = kwargs

    @staticmethod
    def _auto_pick() -> str:
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ELEVENLABS_API_KEY"):
            return "elevenlabs"
        return "piper"  # local fallback

    def synthesize(
        self,
        text: str,
        *,
        voice: str = "alloy",
        format: VoiceFormat = "mp3",
        **kwargs: Any,
    ) -> bytes:
        """Convert `text` to audio bytes.

        Args:
            voice:  provider-specific voice name. OpenAI offers
                    alloy / echo / fable / onyx / nova / shimmer.
            format: audio container — mp3 (default), wav, opus, etc.
        """
        if self.provider == "openai":
            return self._synth_openai(text, voice, format)
        if self.provider == "elevenlabs":
            return self._synth_elevenlabs(text, voice, format)
        if self.provider == "piper":
            return self._synth_piper(text, voice, format)
        raise ValueError(f"Unsupported TTS provider: {self.provider}")

    # --- OpenAI TTS -------------------------------------------------------

    def _synth_openai(self, text: str, voice: str, format: VoiceFormat) -> bytes:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError(
                "OpenAI TTS requires `openai`. Install with:\n"
                '  pip install "praxia[audio]"'
            ) from e

        client = OpenAI()
        response = client.audio.speech.create(
            model=self._kwargs.get("model", "tts-1"),
            voice=voice,
            input=text,
            response_format=format,
        )
        return response.content

    # --- ElevenLabs -------------------------------------------------------

    def _synth_elevenlabs(  # pragma: no cover
        self, text: str, voice: str, format: VoiceFormat
    ) -> bytes:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as e:
            raise ImportError(
                "ElevenLabs TTS requires `elevenlabs`. Install with:\n"
                '  pip install "praxia[audio]"'
            ) from e

        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        # ElevenLabs returns a generator of byte chunks
        chunks = client.text_to_speech.convert(
            voice_id=voice,
            text=text,
            output_format=f"{format}_44100_128" if format == "mp3" else format,
        )
        return b"".join(chunks)

    # --- Local Piper ------------------------------------------------------

    def _synth_piper(self, text: str, voice: str, format: VoiceFormat) -> bytes:  # pragma: no cover
        try:
            from piper import PiperVoice
        except ImportError as e:
            raise ImportError(
                "Local Piper TTS requires `piper-tts`. Install with:\n"
                '  pip install "praxia[audio-local]"'
            ) from e

        import io
        import wave

        v = PiperVoice.load(voice)  # voice = path to .onnx file
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            v.synthesize(text, wav)
        return buffer.getvalue()


# Convenience alias
TextToSpeech = TTS
