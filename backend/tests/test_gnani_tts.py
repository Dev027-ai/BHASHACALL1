"""Unit and integration tests for Gnani Text-to-Speech (Timbre v2.5)."""
import pytest
import os
import wave
import io
import asyncio
from unittest.mock import patch
from app.services.pipeline import (
    synthesize_speech,
    synthesize_speech_stream,
    get_tts_locale,
    get_tts_voice,
    TIMBRE_V25_VOICES,
    DEFAULT_VOICE_MAP,
)


def test_tts_model_configuration():
    """Verify default TTS model is timbre-v2.5."""
    model = os.getenv("GNANI_TTS_MODEL", "timbre-v2.5")
    assert model == "timbre-v2.5"


def test_supported_voice_catalogue():
    """Verify that all default voices belong to the 42 TIMBRE_V25_VOICES catalogue."""
    assert len(TIMBRE_V25_VOICES) == 42
    for lang, voice in DEFAULT_VOICE_MAP.items():
        assert voice in TIMBRE_V25_VOICES
        assert get_tts_voice(lang) == voice


def test_unsupported_voice_handling():
    """Verify that specifying an unsupported voice raises a descriptive error."""
    with patch.dict(os.environ, {"GNANI_TTS_VOICE_HI": "InvalidFakeVoiceName"}):
        with pytest.raises(RuntimeError, match="not in Gnani Timbre v2.5 catalogue"):
            get_tts_voice('hi')


def test_empty_text_tts_error():
    """Verify empty text raises an error."""
    with pytest.raises(RuntimeError, match="empty"):
        asyncio.run(synthesize_speech("", "hi"))


def test_realtime_audio_generation():
    """Verify TTS audio generation returns valid WAV bytes and correct mime type."""
    async def _run():
        with patch.dict(os.environ, {"GNANI_MOCK_MODE": "true"}):
            audio_bytes, mime = await synthesize_speech("नमस्ते", "hi")
            assert mime == "audio/wav"
            assert len(audio_bytes) > 44
            assert audio_bytes.startswith(b"RIFF")

            with wave.open(io.BytesIO(audio_bytes), 'rb') as w:
                assert w.getnchannels() == 1
                assert w.getsampwidth() == 2
                assert w.getframerate() == 48000

    asyncio.run(_run())


def test_incremental_chunk_streaming():
    """Verify streaming TTS yields incremental audio chunks."""
    async def _run():
        with patch.dict(os.environ, {"GNANI_MOCK_MODE": "true"}):
            chunks = []
            async for chunk in synthesize_speech_stream("Hello, welcome to BhashaCall.", "en"):
                chunks.append(chunk)

            assert len(chunks) > 0
            total_bytes = b"".join(chunks)
            assert len(total_bytes) > 0

    asyncio.run(_run())
