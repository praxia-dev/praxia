"""Audio I/O for Praxia — speech-to-text (STT) and text-to-speech (TTS).

Both classes are provider-agnostic facades that pick a sensible default
based on which API key is set.

Speech-to-text providers (in order of priority):
  - OpenAI Whisper API     (OPENAI_API_KEY)
  - Anthropic (when audio support is GA in their API)
  - Local whisper.cpp      (no key needed; requires `whisper-cpp-python`)

Text-to-speech providers:
  - OpenAI TTS             (OPENAI_API_KEY) — 6 voices, MP3/WAV
  - ElevenLabs             (ELEVENLABS_API_KEY) — premium voice cloning
  - Google Cloud TTS       (GCP credentials)
  - Local Piper TTS        (no key, fully on-prem)

Usage:
    from praxia.io.audio import STT, TTS

    text = STT().transcribe(audio_bytes, filename="meeting.wav")
    audio_bytes = TTS().synthesize("Hello world", voice="alloy")
"""
from praxia.io.audio.stt import STT, SpeechToText
from praxia.io.audio.tts import TTS, TextToSpeech

__all__ = ["STT", "SpeechToText", "TTS", "TextToSpeech"]
