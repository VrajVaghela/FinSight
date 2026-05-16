# app/core/voice_handler.py
from __future__ import annotations

import asyncio
import base64
import io
import os
import tempfile
import wave
from typing import Any

from app.config import settings


class VoiceHandler:
    """Handles speech-to-text and text-to-speech through Gemini."""

    def __init__(self, client: Any = None):
        self.client = client
        self.stt_model = os.getenv("STT_MODEL", settings.stt_model)
        self.tts_model = os.getenv("TTS_MODEL", settings.tts_model)
        self.voice = os.getenv("TTS_VOICE", settings.tts_voice)
        self.silence_threshold_bytes = int(
            os.getenv("VAD_SILENCE_BYTES", str(settings.vad_silence_bytes))
        )

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client
        api_key = os.getenv("GEMINI_API_KEY") or settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        from google import genai

        self.client = genai.Client(api_key=api_key)
        return self.client

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe an accumulated audio chunk with Gemini audio understanding."""
        if not audio_bytes:
            return ""

        fd, path = tempfile.mkstemp(suffix=".wav")
        try:
            with os.fdopen(fd, "wb") as audio_file:
                audio_file.write(audio_bytes)

            def _transcribe() -> str:
                client = self._get_client()
                uploaded = client.files.upload(file=path)
                response = client.models.generate_content(
                    model=self.stt_model,
                    contents=[
                        "Transcribe this audio accurately. Return only the transcript text.",
                        uploaded,
                    ],
                )
                return (getattr(response, "text", "") or "").strip()

            return await asyncio.to_thread(_transcribe)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV bytes with Gemini TTS."""
        if not text.strip():
            return b""

        def _synthesize() -> bytes:
            from google.genai import types

            client = self._get_client()
            response = client.models.generate_content(
                model=self.tts_model,
                contents=f"Say clearly: {text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.voice,
                            )
                        )
                    ),
                ),
            )
            inline_data = response.candidates[0].content.parts[0].inline_data.data
            if isinstance(inline_data, str):
                pcm = base64.b64decode(inline_data)
            else:
                pcm = bytes(inline_data)
            return self._pcm_to_wav(pcm)

        return await asyncio.to_thread(_synthesize)

    @staticmethod
    def _pcm_to_wav(pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()

    def detect_silence(self, audio_buffer: bytearray) -> bool:
        """Basic Voice Activity Detection (VAD). Threshold configured via VAD_SILENCE_BYTES."""
        return len(audio_buffer) > self.silence_threshold_bytes
