"""Tests for audio conversion and 16-bit PCM mono 16kHz frame formatting."""
import pytest
import wave
import io
from app.services.pipeline import (
    convert_audio_to_pcm16_mono_wav,
    extract_raw_pcm_from_wav,
    create_silent_wav,
    create_tone_wav,
)


def test_create_and_validate_wav():
    """Verify generated test audio matches 16kHz mono 16-bit PCM specification."""
    wav_bytes = create_silent_wav(duration_seconds=1.0, sample_rate=16000)
    with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        assert w.getnframes() == 16000

    pcm = extract_raw_pcm_from_wav(wav_bytes)
    assert len(pcm) == 32000  # 16000 samples * 2 bytes


def test_frame_size_compliance():
    """Verify that 512 samples corresponds exactly to 1,024 bytes (32 ms frame duration)."""
    wav_bytes = create_tone_wav(freq=440.0, duration_seconds=0.032, sample_rate=16000)
    pcm = extract_raw_pcm_from_wav(wav_bytes)

    # 32ms at 16,000 samples/sec = 512 samples
    # 512 samples * 2 bytes/sample = 1,024 bytes
    assert len(pcm) == 1024


def test_convert_existing_wav_pass_through():
    """Verify WAV converter handles existing 16kHz mono WAV seamlessly."""
    wav_bytes = create_silent_wav(duration_seconds=0.5, sample_rate=16000)
    converted = convert_audio_to_pcm16_mono_wav(wav_bytes, sample_rate=16000)
    assert converted.startswith(b"RIFF")
    with wave.open(io.BytesIO(converted), 'rb') as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
