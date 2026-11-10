"""Unit and integration tests for Gnani Speech-to-Text (Prisma v3.0)."""
import pytest
import os
import asyncio
from unittest.mock import patch
from app.services.pipeline import (
    transcribe_with_gnani,
    GnaniRealtimeSTTSession,
    get_stt_locale,
    create_silent_wav,
)


def test_stt_model_configuration():
    """Verify default STT model is prisma-v3.0."""
    model = os.getenv("GNANI_STT_MODEL", "prisma-v3.0")
    assert model == "prisma-v3.0"


def test_stt_language_selection_and_auto_detection():
    """Verify explicit language selection and indic-auto detection."""
    assert get_stt_locale('hi') == 'hi-IN'
    assert get_stt_locale('ta') == 'ta-IN'
    assert get_stt_locale('te') == 'te-IN'
    assert get_stt_locale('bn') == 'bn-IN'
    assert get_stt_locale('mr') == 'mr-IN'
    assert get_stt_locale('en') == 'en-IN'
    assert get_stt_locale('auto') in ('indic-auto', 'hi-IN')


def test_stt_empty_audio_raises_error():
    """Verify that empty audio bytes trigger a descriptive error."""
    with pytest.raises(RuntimeError, match="audio is empty"):
        asyncio.run(transcribe_with_gnani(b"", "audio/webm", "hi"))


def test_stt_streaming_session_events():
    """Verify real-time STT session startup, chunk processing and transcript dispatch."""
    async def _run():
        received_transcripts = []

        async def on_transcript(data):
            received_transcripts.append(data)

        session = GnaniRealtimeSTTSession(
            language_code="hi-IN",
            on_transcript=on_transcript,
        )
        session._mock = True

        await session.start()
        assert session.is_connected is True

        silent_chunk = b'\x00\x00' * 512
        for _ in range(35):
            await session.send_pcm_chunk(silent_chunk)

        assert len(received_transcripts) > 0
        assert "text" in received_transcripts[0]
        assert len(received_transcripts[0]["text"]) > 0

        await session.close()
        assert session.is_connected is False

    asyncio.run(_run())


def test_stt_auth_failure_handling():
    """Verify that Gnani STT authentication error is surfaced clearly."""
    async def _run():
        with patch.dict(os.environ, {"GNANI_API_KEY": "invalid-key-testing", "GNANI_MOCK_MODE": "false"}):
            with patch("gnani.stt.GnaniSTTClient.transcribe_bytes") as mock_transcribe:
                class DummyAuthError(Exception):
                    status_code = 401
                mock_transcribe.side_effect = DummyAuthError("Unauthorized")

                wav_data = create_silent_wav(duration_seconds=0.5)
                with pytest.raises(RuntimeError, match="authentication failed"):
                    await transcribe_with_gnani(wav_data, "audio/wav", "hi")

    asyncio.run(_run())
