"""Provider adapters for BhashaCall.
Gnani.ai is the central speech engine (Prisma v3.0 for STT, Timbre v2.5 for TTS).

Supported languages (6 Indian locales):
- Hindi: hi-IN
- English (India): en-IN
- Bengali: bn-IN
- Tamil: ta-IN
- Telugu: te-IN
- Marathi: mr-IN
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
import logging
import math
import os
import re
import socket
import struct
import threading
import time
import unicodedata
import uuid
import wave
from typing import Any, AsyncIterator, Callable, Coroutine
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("bhashacall.pipeline")

# Lara SDK client is synchronous; reuse one authenticated client and run calls
# in a worker thread so the FastAPI/WebSocket event loop remains responsive.
_LARA_TRANSLATOR: Any | None = None
_LARA_CREDENTIALS: tuple[str, str] | None = None
_LARA_LOCK = threading.Lock()


# ============================================================================
# 1. LANGUAGE AND VOICE CATALOGUE SPECIFICATION
# ============================================================================

SUPPORTED_LANGUAGE_LOCALES: dict[str, str] = {
    'hi': 'hi-IN',
    'en': 'en-IN',
    'bn': 'bn-IN',
    'ta': 'ta-IN',
    'te': 'te-IN',
    'mr': 'mr-IN',
}

LANGUAGE_NAMES: dict[str, str] = {
    'hi': 'Hindi',
    'en': 'English (India)',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'mr': 'Marathi',
}

# The verified 42-voice catalogue supported by Gnani Timbre v2.5:
TIMBRE_V25_VOICES: frozenset[str] = frozenset({
    'Ambuja', 'Asmita', 'Bhavna', 'Brinda', 'Chitra', 'Deepak', 'Devika',
    'Dhruva', 'Falak', 'Girish', 'Hemraj', 'Ishaan', 'Jalaj', 'Jwala',
    'Kaveri', 'Kavin', 'Kirra', 'Lavanya', 'Lehara', 'Mehuli', 'Nalini',
    'Noopur', 'Omkar', 'Poorvi', 'Pranav', 'Reshma', 'Riyaan', 'Roopesh',
    'Saanvi', 'Shlok', 'Suhana', 'Trisha', 'Trupti', 'Urmila', 'Varuni',
    'Vedika', 'Veera', 'Vikrant', 'Yashvi', 'Yukti', 'Zahira', 'Zayan',
})

# Verified default voice assignments for the 6 languages:
DEFAULT_VOICE_MAP: dict[str, str] = {
    'hi': 'Nalini',
    'en': 'Kaveri',
    'bn': 'Mehuli',
    'ta': 'Kavin',
    'te': 'Lavanya',
    'mr': 'Asmita',
}

VOICE_ENV_VARS: dict[str, str] = {
    'hi': 'GNANI_TTS_VOICE_HI',
    'en': 'GNANI_TTS_VOICE_EN',
    'bn': 'GNANI_TTS_VOICE_BN',
    'ta': 'GNANI_TTS_VOICE_TA',
    'te': 'GNANI_TTS_VOICE_TE',
    'mr': 'GNANI_TTS_VOICE_MR',
}

LANGUAGE_ENV_VARS: dict[str, str] = {
    'hi': 'GNANI_TTS_LANGUAGE_HI',
    'en': 'GNANI_TTS_LANGUAGE_EN',
    'bn': 'GNANI_TTS_LANGUAGE_BN',
    'ta': 'GNANI_TTS_LANGUAGE_TA',
    'te': 'GNANI_TTS_LANGUAGE_TE',
    'mr': 'GNANI_TTS_LANGUAGE_MR',
}

STT_LANGUAGE_ENV_VARS: dict[str, str] = {
    'hi': 'GNANI_STT_LANGUAGE_HI',
    'en': 'GNANI_STT_LANGUAGE_EN',
    'bn': 'GNANI_STT_LANGUAGE_BN',
    'ta': 'GNANI_STT_LANGUAGE_TA',
    'te': 'GNANI_STT_LANGUAGE_TE',
    'mr': 'GNANI_STT_LANGUAGE_MR',
}


def normalize_unicode_text(value: Any) -> str:
    """Preserve user/STT text as valid UTF-8 and normalize canonically (NFC)."""
    if value is None:
        return ''
    text = str(value)
    try:
        # Strict round-trip rejects lone surrogate code points instead of silently
        # replacing or dropping characters at an API/JSON boundary.
        text = text.encode('utf-8', errors='strict').decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise ValueError('Transcript contains invalid Unicode; please retry the utterance.') from exc
    if '\ufffd' in text:
        raise ValueError('Transcript contains Unicode replacement characters; please retry the utterance.')
    return unicodedata.normalize('NFC', text)


def _looks_like_corrupted_hindi(text: str, source: str) -> bool:
    """Catch obvious terminal/encoding damage before sending Hindi to translation."""
    if source != 'hi':
        return False
    has_devanagari = any('\u0900' <= ch <= '\u097f' for ch in text)
    has_letters_or_digits = any(ch.isalnum() for ch in text)
    return not has_devanagari and not has_letters_or_digits and bool(re.search(r'\?{2,}', text))


def _lang(language: str) -> str:
    """Normalize language tag (e.g. hi-IN -> hi, auto -> auto)."""
    val = (language or 'auto').strip().lower().replace('_', '-')
    if val in ('', 'auto'):
        return 'auto'
    return val.split('-', 1)[0]


def get_stt_locale(language: str) -> str:
    """Get the BCP-47 locale for STT (configured or default)."""
    code = _lang(language)
    if code == 'auto':
        return os.getenv('GNANI_STT_LANGUAGE', 'indic-auto').strip() or 'indic-auto'
    default_loc = SUPPORTED_LANGUAGE_LOCALES.get(code, 'hi-IN')
    env_name = STT_LANGUAGE_ENV_VARS.get(code)
    if env_name:
        configured = os.getenv(env_name, '').strip()
        if configured:
            return configured
    return default_loc


def get_tts_locale(language: str) -> str:
    """Get the BCP-47 locale for TTS (configured or default)."""
    code = _lang(language)
    default_loc = SUPPORTED_LANGUAGE_LOCALES.get(code, 'hi-IN')
    env_name = LANGUAGE_ENV_VARS.get(code)
    if env_name:
        configured = os.getenv(env_name, '').strip()
        if configured:
            return configured
    return default_loc


def get_tts_voice(language: str) -> str:
    """Get the verified voice name for a given language."""
    code = _lang(language)
    env_name = VOICE_ENV_VARS.get(code)
    configured_voice = os.getenv(env_name, '').strip() if env_name else ''
    if not configured_voice and code in ('hi', 'en'):
        configured_voice = os.getenv('GNANI_TTS_VOICE', '').strip()

    voice = configured_voice or DEFAULT_VOICE_MAP.get(code, 'Nalini')
    if voice not in TIMBRE_V25_VOICES:
        raise RuntimeError(
            f"Voice '{voice}' is not in Gnani Timbre v2.5 catalogue of 42 voices. "
            f"Choose from: {', '.join(sorted(TIMBRE_V25_VOICES))}"
        )
    return voice


def get_gnani_api_key() -> str:
    """Retrieve the configured Gnani API key."""
    return os.getenv('GNANI_API_KEY', '').strip()


def is_mock_mode() -> bool:
    """Determine whether mock/test mode is active (e.g. no key or mock flag)."""
    if os.getenv('GNANI_MOCK_MODE', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    key = get_gnani_api_key()
    return not key or key.startswith('mock-') or key == 'test-key'


# ============================================================================
# 2. AUDIO CONVERSION & PROCESSING (16kHz mono 16-bit PCM)
# ============================================================================

def convert_audio_to_pcm16_mono_wav(audio_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Decode WebM/Opus/WAV/MP3 into 16-bit mono PCM WAV at specified sample rate."""
    if not audio_bytes:
        raise RuntimeError("Audio bytes are empty.")

    # If it is already a WAV with correct rate and channels, return as is
    if audio_bytes.startswith(b'RIFF'):
        try:
            with wave.open(io.BytesIO(audio_bytes), 'rb') as w:
                if w.getnchannels() == 1 and w.getframerate() == sample_rate and w.getsampwidth() == 2:
                    return audio_bytes
        except Exception:
            pass

    try:
        import av
    except ImportError as exc:
        raise RuntimeError("av library is required for audio decoding. Install av.") from exc

    try:
        with av.open(io.BytesIO(audio_bytes)) as container:
            audio_stream = next(
                (stream for stream in container.streams if stream.type == "audio"),
                None
            )
            if audio_stream is None:
                raise RuntimeError("No audio stream was found in the recording.")

            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=sample_rate
            )

            pcm = bytearray()
            for frame in container.decode(audio_stream):
                for converted in resampler.resample(frame):
                    pcm.extend(converted.to_ndarray().tobytes())

            for converted in resampler.resample(None):
                pcm.extend(converted.to_ndarray().tobytes())

            if not pcm:
                raise RuntimeError("The recording contains no decodable audio.")

            output = io.BytesIO()
            with wave.open(output, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(bytes(pcm))

            return output.getvalue()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Could not decode audio ({type(exc).__name__}): {exc}. "
            "Try recording again."
        ) from exc


def extract_raw_pcm_from_wav(wav_bytes: bytes) -> bytes:
    """Extract raw PCM bytes from a WAV container."""
    with wave.open(io.BytesIO(wav_bytes), 'rb') as w:
        return w.readframes(w.getnframes())


def create_silent_wav(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Create a silent WAV file for testing."""
    num_samples = int(sample_rate * duration_seconds)
    pcm = b'\x00\x00' * num_samples
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm)
    return output.getvalue()


def create_tone_wav(freq: float = 440.0, duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Create a sine tone WAV file for test playback."""
    num_samples = int(sample_rate * duration_seconds)
    buf = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(16000 * math.sin(2 * math.pi * freq * t))
        buf.extend(struct.pack('<h', sample))
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(buf))
    return output.getvalue()


# ============================================================================
# 3. GNANI SPEECH-TO-TEXT (STT) — PRISMA V3.0
# ============================================================================

async def transcribe_with_gnani(
    audio_bytes: bytes,
    mime_type: str = "audio/webm",
    language: str = "hi"
) -> str:
    """Transcribe a recorded phrase using Gnani's Prisma v3.0 model.

    Decodes input to 16 kHz mono WAV and invokes GnaniSTTClient.transcribe_bytes
    with model='prisma-v3.0'.
    """
    if not audio_bytes:
        raise RuntimeError("The recorded audio is empty.")

    # Handle Mock mode for tests or when key is absent
    if is_mock_mode():
        return _mock_stt_transcribe(language)

    key = get_gnani_api_key()
    if not key:
        raise RuntimeError("Missing GNANI_API_KEY. Configure it in backend/.env.")

    from gnani.stt import GnaniSTTClient

    code = _lang(language)
    locale = get_stt_locale(code)

    wav_bytes = await asyncio.to_thread(convert_audio_to_pcm16_mono_wav, audio_bytes, 16000)

    # Prisma v3.0 formatting: use codemix for Hinglish or verbatim
    stt_format = "codemix" if code in ('hi', 'auto') else "verbatim"
    candidates = ['hi-IN', 'en-IN', 'bn-IN', 'ta-IN', 'te-IN', 'mr-IN'] if locale == 'indic-auto' else None

    def _call_gnani():
        client = GnaniSTTClient(api_key=key)
        return client.transcribe_bytes(
            wav_bytes,
            filename="bhashacall-phrase.wav",
            language_code=locale,
            model="prisma-v3.0",
            format=stt_format,
            language_candidates=candidates,
        )

    try:
        result = await asyncio.to_thread(_call_gnani)
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if status in (401, 403):
            raise RuntimeError(
                "Gnani STT authentication failed (401/403). Check GNANI_API_KEY."
            ) from exc
        if status == 429:
            raise RuntimeError("Gnani STT rate limit reached. Retry later.") from exc
        raise RuntimeError(f"Gnani STT request failed ({type(exc).__name__}): {exc}") from exc

    transcript = result.get("transcript") if isinstance(result, dict) else None
    if not isinstance(transcript, str) or not transcript.strip():
        raise RuntimeError("Gnani STT returned an empty transcript.")
    return transcript.strip()


class GnaniRealtimeSTTSession:
    """Manages a real-time streaming STT session to Gnani Prisma v3.0 over WebSocket.

    Complies with Gnani's real-time streaming protocol:
    - 16-bit PCM little-endian mono, 16,000 Hz
    - 1,024-byte frames (512 samples = 32 ms)
    - Emits StreamTranscriptEvent with text and detected_language_code
    """

    def __init__(
        self,
        language_code: str = "indic-auto",
        on_transcript: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None,
        api_key: str | None = None,
    ):
        self.language_code = language_code
        self.on_transcript = on_transcript
        self.api_key = api_key or get_gnani_api_key()
        self.is_connected = False
        self._client: Any = None
        self._buffer = bytearray()
        self._read_task: asyncio.Task | None = None
        self._closed = False
        self._mock = is_mock_mode()
        self._mock_counter = 0

    async def start(self) -> None:
        """Start the real-time STT session."""
        if self._mock:
            self.is_connected = True
            logger.info("[Mock STT] Realtime session started in mock mode.")
            return

        from gnani.stt import GnaniSTTStreamClient

        candidates = ['hi-IN', 'en-IN', 'bn-IN', 'ta-IN', 'te-IN', 'mr-IN'] if self.language_code == 'indic-auto' else None

        self._client = GnaniSTTStreamClient(
            api_key=self.api_key,
            language_code=self.language_code,
            model="prisma-v3.0",
            language_candidates=candidates,
            sample_rate=16000,
            format="codemix" if self.language_code in ('hi-IN', 'indic-auto') else "transcribe",
        )

        try:
            await self._client.connect()
            self.is_connected = True
            self._read_task = asyncio.create_task(self._read_events_loop())
            logger.info("[STT WS] Connected to Gnani Prisma v3.0 STT stream.")
        except Exception as exc:
            self.is_connected = False
            logger.error("[STT WS] Connection failed: %s", exc)
            raise RuntimeError(f"Gnani STT WebSocket stream connection failed: {exc}") from exc

    async def _read_events_loop(self) -> None:
        """Read transcript events from GnaniSTTStreamClient."""
        from gnani.stt import StreamTranscriptEvent

        try:
            async for event in self._client:
                if isinstance(event, StreamTranscriptEvent) and event.text.strip():
                    data = {
                        "text": event.text.strip(),
                        "detected_language_code": getattr(event, "detected_language_code", None) or self.language_code,
                        "audio_duration_ms": getattr(event, "audio_duration_ms", 0),
                        "latency": getattr(event, "latency", None),
                        "timestamp": getattr(event, "timestamp", time.time()),
                    }
                    if self.on_transcript:
                        await self.on_transcript(data)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("[STT WS] Read loop encountered: %s", exc)
        finally:
            self.is_connected = False

    async def send_pcm_chunk(self, chunk: bytes) -> None:
        """Send a chunk of 16-bit PCM mono 16kHz audio.

        Buffers and packetizes into exactly 1,024-byte frames (512 samples / 32 ms).
        """
        if self._closed or not self.is_connected:
            return

        if self._mock:
            await self._handle_mock_chunk(chunk)
            return

        self._buffer.extend(chunk)
        # Frame size = 1024 bytes (512 samples of 16-bit mono PCM = 32ms)
        FRAME_SIZE = 1024
        while len(self._buffer) >= FRAME_SIZE:
            frame = bytes(self._buffer[:FRAME_SIZE])
            del self._buffer[:FRAME_SIZE]
            if self._client and self._client.is_connected:
                await self._client.send_audio(frame)

    async def _handle_mock_chunk(self, chunk: bytes) -> None:
        """Simulate transcript generation for testing."""
        self._buffer.extend(chunk)
        # Every ~32,000 bytes (1 second of audio), trigger a mock transcript
        if len(self._buffer) >= 32000:
            self._buffer.clear()
            self._mock_counter += 1
            code = self.language_code.split('-')[0] if '-' in self.language_code else self.language_code
            if code == 'indic-auto':
                code = 'hi'
            sample_text = _mock_stt_transcribe(code)
            if self.on_transcript:
                await self.on_transcript({
                    "text": sample_text,
                    "detected_language_code": SUPPORTED_LANGUAGE_LOCALES.get(code, "hi-IN"),
                    "audio_duration_ms": 1000,
                    "latency": 85,
                    "timestamp": time.time(),
                })

    async def close(self) -> None:
        """Close the STT session."""
        self._closed = True
        self.is_connected = False
        if self._read_task:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._read_task
        if self._client:
            with contextlib.suppress(Exception):
                await self._client.close()


def _mock_stt_transcribe(language: str) -> str:
    """Mock transcripts for testing without live credits."""
    code = _lang(language)
    samples = {
        'hi': 'नमस्ते, आप कैसे हैं? मुझे खुशी है कि हम बात कर रहे हैं।',
        'en': 'Hello, how are you? I am glad we are talking.',
        'bn': 'নমস্কার, আপনি কেমন আছেন? আপনার সাথে কথা বলে ভালো লাগছে।',
        'ta': 'வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்? உங்களுடன் பேசுவதில் மகிழ்ச்சி.',
        'te': 'నమస్కారం, మీరు ఎలా ఉన్నారు? మీతో మాట్లాడటం ఆనందంగా ఉంది.',
        'mr': 'नमस्कार, तुम्ही कसे आहात? तुमच्याशी बोलून आनंद झाला.',
    }
    return samples.get(code, samples['hi'])


# ============================================================================
# 4. GNANI TEXT-TO-SPEECH (TTS) — TIMBRE V2.5
# ============================================================================

async def synthesize_with_gnani(text: str, language: str) -> tuple[bytes, str]:
    """Synthesize speech using Gnani Timbre v2.5 over WebSocket.

    Uses gnani.tts.GnaniTTSRealtimeClient.synthesize_and_collect.
    Returns (wav_bytes, 'audio/wav').
    """
    clean_text = normalize_unicode_text(text).strip()
    if not clean_text:
        raise RuntimeError("Text to synthesize is empty.")

    code = _lang(language)
    locale = get_tts_locale(code)
    voice = get_tts_voice(code)
    speed = float(os.getenv('GNANI_TTS_SPEED', '1.0'))
    speed = max(0.85, min(1.15, speed))
    sample_rate = int(os.getenv('GNANI_TTS_SAMPLE_RATE', '48000'))

    # Mock mode handling for credit-conservation / automated tests
    if is_mock_mode():
        return create_tone_wav(freq=440.0, duration_seconds=0.6, sample_rate=sample_rate), 'audio/wav'

    key = get_gnani_api_key()
    if not key:
        raise RuntimeError("Missing GNANI_API_KEY. Configure it in backend/.env.")

    from gnani.tts import GnaniTTSRealtimeClient, AudioConfig

    cfg = AudioConfig(
        sample_rate=sample_rate,
        encoding='linear_pcm',
        num_channels=1,
        sample_width=2,
        container='wav'
    )

    try:
        async with GnaniTTSRealtimeClient(api_key=key) as client:
            audio_bytes = await client.synthesize_and_collect(
                text=clean_text,
                voice=voice,
                model="timbre-v2.5",
                language=locale,
                speed=speed,
                audio_config=cfg,
            )
            if not audio_bytes:
                raise RuntimeError("Gnani TTS returned empty audio data.")
            return audio_bytes, 'audio/wav'
    except Exception as exc:
        status = getattr(exc, 'status_code', None)
        detail = str(exc)
        if 'auth' in detail.lower() or status in (401, 403):
            raise RuntimeError(
                "Gnani TTS authentication failed. Verify API key and Timbre entitlements."
            ) from exc
        raise RuntimeError(f"Gnani TTS synthesis failed ({type(exc).__name__}): {detail}") from exc


async def synthesize_speech(text: str, language: str) -> tuple[bytes, str]:
    """Public wrapper for speech synthesis."""
    return await synthesize_with_gnani(text, language)


async def synthesize_speech_stream(text: str, language: str) -> AsyncIterator[bytes]:
    """Yield streaming audio chunks from Gnani Timbre v2.5."""
    clean_text = normalize_unicode_text(text).strip()
    if not clean_text:
        return

    code = _lang(language)
    locale = get_tts_locale(code)
    voice = get_tts_voice(code)
    speed = float(os.getenv('GNANI_TTS_SPEED', '1.0'))
    speed = max(0.85, min(1.15, speed))
    sample_rate = int(os.getenv('GNANI_TTS_SAMPLE_RATE', '48000'))

    if is_mock_mode():
        yield create_tone_wav(freq=440.0, duration_seconds=0.4, sample_rate=sample_rate)
        return

    key = get_gnani_api_key()
    from gnani.tts import GnaniTTSRealtimeClient, AudioConfig

    cfg = AudioConfig(
        sample_rate=sample_rate,
        encoding='linear_pcm',
        num_channels=1,
        sample_width=2,
        container='wav'
    )

    async with GnaniTTSRealtimeClient(api_key=key) as client:
        async for chunk in client.synthesize(
            text=clean_text,
            voice=voice,
            model="timbre-v2.5",
            language=locale,
            speed=speed,
            audio_config=cfg,
        ):
            yield chunk


# ============================================================================
# 5. TRANSLATION ENGINE & HINGLISH UNDERSTANDING
# ============================================================================

# Common conversational dictionary across all 6 languages (Hindi, English, Bengali, Tamil, Telugu, Marathi)
_CONVERSATIONAL_CORPUS: dict[str, dict[str, str]] = {
    "hello": {
        "hi": "नमस्ते", "en": "Hello", "bn": "নমস্কার",
        "ta": "வணக்கம்", "te": "నమస్కారం", "mr": "नमस्कार"
    },
    "how are you": {
        "hi": "आप कैसे हैं?", "en": "How are you?", "bn": "আপনি কেমন আছেন?",
        "ta": "நீங்கள் எப்படி இருக்கிறீர்கள்?", "te": "మీరు ఎలా ఉన్నారు?", "mr": "तुम्ही कसे आहात?"
    },
    "i am fine": {
        "hi": "मैं ठीक हूँ।", "en": "I am fine.", "bn": "আমি ভালো আছি।",
        "ta": "நான் நலமாக இருக்கிறேன்.", "te": "నేను బాగున్నాను.", "mr": "मी ठीक आहे."
    },
    "what is your name": {
        "hi": "आपका नाम क्या है?", "en": "What is your name?", "bn": "আপনার নাম কী?",
        "ta": "உங்கள் பெயர் என்ன?", "te": "మీ పేరు ఏమిటి?", "mr": "तुमचे नाव काय आहे?"
    },
    "my name is bhashacall": {
        "hi": "मेरा नाम भाषाकॉल है।", "en": "My name is BhashaCall.", "bn": "আমার নাম ভাষাকল।",
        "ta": "என் பெயர் பாஷாகால்.", "te": "నా పేరు భాషాకాల్.", "mr": "माझे नाव भाषाकॉल आहे."
    },
    "can you hear me": {
        "hi": "क्या आप मुझे सुन सकते हैं?", "en": "Can you hear me?", "bn": "আপনি কি আমাকে শুনতে পাচ্ছেন?",
        "ta": "நீங்கள் என்னைக் கேட்க முடிகிறதா?", "te": "మీరు నన్ను వినగలరా?", "mr": "तुम्ही मला ऐकू शकता का?"
    },
    "yes i can hear you": {
        "hi": "हाँ, मैं आपको सुन सकता हूँ।", "en": "Yes, I can hear you.", "bn": "হ্যাঁ, আমি আপনাকে শুনতে পাচ্ছি।",
        "ta": "ஆம், நான் உங்களை கேட்க முடிகிறது.", "te": "అవును, నేను మిమ్మల్ని వినగలను.", "mr": "होय, मी तुम्हाला ऐकू शकतो."
    },
    "speak in your own language": {
        "hi": "अपनी भाषा में बोलें।", "en": "Speak in your own language.", "bn": "আপনার নিজের ভাষায় কথা বলুন।",
        "ta": "உங்கள் சொந்த மொழியில் பேசுங்கள்.", "te": "మీ స్వంత భాషలో మాట్లాడండి.", "mr": "तुमच्या स्वतःच्या भाषेत बोला."
    },
    "thank you": {
        "hi": "धन्यवाद", "en": "Thank you", "bn": "ধন্যবাদ",
        "ta": "நன்றி", "te": "ధన్యవాదాలు", "mr": "धन्यवाद"
    },
    "good morning": {
        "hi": "शुभ प्रभात", "en": "Good morning", "bn": "সুপ্রভাত",
        "ta": "காலை வணக்கம்", "te": "శుభోదయం", "mr": "शुभ सकाळ"
    },
    "good evening": {
        "hi": "शुभ संध्या", "en": "Good evening", "bn": "শুভ সন্ধ্যা",
        "ta": "மாலை வணக்கம்", "te": "శుభ సాయంత్రం", "mr": "शुभ संध्याकाळ"
    },
    "why do you think so": {
        "hi": "आपको ऐसा क्यों लगता है?", "en": "Why do you think so?", "bn": "আপনি কেন এমন মনে করেন?",
        "ta": "நீங்கள் ஏன் அப்படி நினைக்கிறீர்கள்?", "te": "మీరు ఎందుకు అలా అనుకుంటున్నారు?", "mr": "तुम्हाला असे का वाटते?"
    },
    "i have to go to office tomorrow": {
        "hi": "मुझे कल ऑफिस जाना है।", "en": "I have to go to office tomorrow.", "bn": "আমাকে কাল অফিসে যেতে হবে।",
        "ta": "நான் நாளை அலுவலகத்திற்கு செல்ல வேண்டும்.", "te": "నేను రేపు ఆఫీసుకు వెళ్ళాలి.", "mr": "मला उद्या ऑफिसला जायचे आहे."
    },
    "can you please call me": {
        "hi": "क्या आप कृपया मुझे कॉल कर सकते हैं?", "en": "Can you please call me?", "bn": "আপনি কি দয়া করে আমাকে কল করতে পারেন?",
        "ta": "தயவுசெய்து என்னை அழைக்க முடியுமா?", "te": "దయచేసి నాకు కాల్ చేయగలరా?", "mr": "तुम्ही मला कृपया कॉल करू शकता का?"
    },
    "where are you going": {
        "hi": "आप कहाँ जा रहे हैं?", "en": "Where are you going?", "bn": "আপনি কোথায় যাচ্ছেন?",
        "ta": "நீங்கள் எங்கே போகிறீர்கள்?", "te": "మీరు ఎక్కడికి వెళ్తున్నారు?", "mr": "तुम्ही कुठे जात आहात?"
    },
    "welcome to bhashacall": {
        "hi": "भाषाकॉल में आपका स्वागत है।", "en": "Welcome to BhashaCall.", "bn": "ভাষাকলে আপনাকে স্বাগতম।",
        "ta": "பாஷாகாலுக்கு உங்களை வரவேற்கிறோம்.", "te": "భాషాకాల్‌కు స్వాగతం.", "mr": "भाषाकॉलमध्ये आपले स्वागत आहे."
    }
}

# Hinglish vocabulary & transliteration dictionary
_HINGLISH_WORDS = {
    'hai', 'hain', 'ho', 'hu', 'haan', 'nahi', 'nahin', 'kyu', 'kyon', 'kyunki', 'kya',
    'kaise', 'kaisa', 'kaisi', 'tum', 'tumhe', 'tumhein', 'tumko', 'aap', 'apko',
    'mujhe', 'mera', 'meri', 'mere', 'tera', 'teri', 'tere', 'ham', 'hum', 'hume', 'humein',
    'aisa', 'aesi', 'aese', 'waisa', 'waise', 'lagta', 'lagti', 'lagte', 'accha',
    'achha', 'acha', 'theek', 'thik', 'kar', 'karo', 'karta', 'karte', 'karna', 'batao',
    'bolo', 'matlab', 'abhi', 'kal', 'ka', 'ki', 'ke', 'se', 'bhi', 'bahut', 'bohot',
    'kuch', 'koi', 'kyun', 'kaun', 'kab', 'kahan', 'yahan', 'wahan', 'pata', 'samajh', 'yaar', 'office', 'jaana'
}

_HINGLISH_DEVANAGARI = {
    'kyu': 'क्यों', 'kyon': 'क्यों', 'kyunki': 'क्योंकि', 'tumhe': 'तुम्हें',
    'tumhein': 'तुम्हें', 'aesa': 'ऐसा', 'aisa': 'ऐसा', 'aesi': 'ऐसी',
    'aese': 'ऐसे', 'hai': 'है', 'hain': 'हैं', 'lagta': 'लगता', 'lagti': 'लगती',
    'lagte': 'लगते', 'mujhe': 'मुझे', 'kya': 'क्या', 'kaise': 'कैसे',
    'kaisa': 'कैसा', 'kaisi': 'कैसी', 'nahi': 'नहीं', 'nahin': 'नहीं',
    'tum': 'तुम', 'tumko': 'तुमको', 'aap': 'आप', 'ho': 'हो', 'haan': 'हाँ',
    'batao': 'बता बताओ', 'bolo': 'बोलो', 'mera': 'मेरा', 'meri': 'मेरी',
    'mere': 'मेरे', 'accha': 'अच्छा', 'achha': 'अच्छा', 'acha': 'अच्छा',
    'kyun': 'क्यों', 'kuch': 'कुछ', 'bahut': 'बहुत', 'bohot': 'बहुत',
    'abhi': 'अभी', 'kaun': 'कौन', 'kab': 'कब', 'kahan': 'कहाँ',
    'yahan': 'यहाँ', 'wahan': 'वहाँ', 'samajh': 'समझ', 'pata': 'पता',
    'yaar': 'यार', 'kal': 'कल', 'office': 'ऑफिस', 'jaana': 'जाना', 'call': 'कॉल',
    'theek': 'ठीक', 'thik': 'ठीक', 'namaste': 'नमस्ते'
}

_KNOWN_HINGLISH_SENTENCES = {
    'kyu tumhe aesa kyu lagta hai': 'Why do you think so?',
    'kyu tumhe aisa kyu lagta hai': 'Why do you think so?',
    'kyun tumhe aisa kyun lagta hai': 'Why do you think so?',
    'kyun tumhe aesa kyun lagta hai': 'Why do you think so?',
    'yaar mujhe kal office jaana hai': 'Friend, I have to go to office tomorrow.',
    'can you please mujhe call karna': 'Can you please call me?',
    'aap kaise ho': 'How are you?',
    'kya chal raha hai': 'What is going on?',
    'main theek hoon': 'I am fine.',
    'dhanyawad': 'Thank you.',
}


def _detect_chat_source(text: str, fallback_source: str = 'en') -> str:
    """Detect whether a Latin-script chat message is Hinglish or English."""
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'
    words = re.findall(r"[a-zA-Z']+", text.lower())
    hits = sum(1 for word in words if word in _HINGLISH_WORDS)
    if hits >= 2 or (hits >= 1 and len(words) <= 3 and words and words[0] in {'hai', 'hain', 'nahi', 'kyu', 'kyon', 'haan', 'yaar'}):
        return 'hi'
    return _lang(fallback_source)


def _detect_script_language(text: str) -> str | None:
    """Detect script for the 6 languages."""
    script_patterns = (
        ('hi', r'[\u0900-\u097F]'),  # Devanagari (Hindi / Marathi)
        ('bn', r'[\u0980-\u09FF]'),  # Bengali
        ('ta', r'[\u0B80-\u0BFF]'),  # Tamil
        ('te', r'[\u0C00-\u0C7F]'),  # Telugu
    )
    for language, pattern in script_patterns:
        if re.search(pattern, text):
            return language
    return None


async def _roman_hinglish_to_devanagari(text: str) -> str:
    """Transliterate Roman-script Hinglish to Devanagari."""
    # First attempt online Google Input Tools if network reachable
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4, connect=2)) as client:
            response = await client.get(
                'https://inputtools.google.com/request',
                params={'text': text, 'itc': 'hi-t-i0-und', 'num': 5},
            )
            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, list) and len(payload) > 1 and payload[0] == 'SUCCESS':
                    candidates = payload[1][0][1]
                    for candidate in candidates:
                        if isinstance(candidate, str) and re.search(r'[\u0900-\u097F]', candidate):
                            return candidate
    except Exception:
        pass

    # Offline dictionary transliteration
    words = text.split()
    converted: list[str] = []
    for w in words:
        clean = re.sub(r'[^a-zA-Z]', '', w.lower())
        dev = _HINGLISH_DEVANAGARI.get(clean)
        converted.append(dev if dev else w)
    result = " ".join(converted)
    if re.search(r'[\u0900-\u097F]', result):
        return result
    return text


def _lookup_corpus_translation(clean_text: str, source: str, target: str) -> str | None:
    """Match exact phrases in either the English key or selected source language."""
    def normalize(value: str) -> str:
        value = unicodedata.normalize("NFC", value).casefold()
        return " ".join(re.sub(r"[^\w\s]", "", value, flags=re.UNICODE).split())

    normalized = normalize(clean_text)
    if not normalized:
        return None

    for phrase, translations in _CONVERSATIONAL_CORPUS.items():
        english_match = normalize(phrase) == normalized
        source_match = normalize(translations.get(source, "")) == normalized

        if english_match or source_match:
            result = translations.get(target)
            if result:
                return result

    en_version = _KNOWN_HINGLISH_SENTENCES.get(normalized)
    if en_version:
        if target == "en":
            return en_version
        return _CONVERSATIONAL_CORPUS.get(normalize(en_version), {}).get(target)

    return None


def _get_lara_translator():
    """Create/reuse Lara SDK translator from server-side environment secrets."""
    global _LARA_TRANSLATOR, _LARA_CREDENTIALS
    access_key_id = os.getenv('LARA_ACCESS_KEY_ID', '').strip()
    access_key_secret = os.getenv('LARA_ACCESS_KEY_SECRET', '').strip()
    if not access_key_id or not access_key_secret:
        raise RuntimeError(
            'Lara translation is not configured. Add LARA_ACCESS_KEY_ID and '
            'LARA_ACCESS_KEY_SECRET to the backend environment.'
        )

    credentials_key = (access_key_id, access_key_secret)
    with _LARA_LOCK:
        if _LARA_TRANSLATOR is None or _LARA_CREDENTIALS != credentials_key:
            try:
                from lara_sdk import Credentials, Translator
            except ImportError as exc:
                raise RuntimeError(
                    'Lara SDK is not installed. Install the backend dependency lara-sdk.'
                ) from exc
            credentials = Credentials(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
            )
            _LARA_TRANSLATOR = Translator(credentials)
            _LARA_CREDENTIALS = credentials_key
    return _LARA_TRANSLATOR


def _translate_with_lara(text: str, source: str, target: str) -> str:
    """Perform one privacy-preserving Lara translation in a worker thread."""
    translator = _get_lara_translator()
    source_locale = SUPPORTED_LANGUAGE_LOCALES[source]
    target_locale = SUPPORTED_LANGUAGE_LOCALES[target]
    result = translator.translate(
        text,
        source=source_locale,
        target=target_locale,
        style='faithful',
        no_trace=True,
        timeout_ms=int(os.getenv('LARA_TIMEOUT_MS', '4500')),
    )
    translated = getattr(result, 'translation', None)
    if isinstance(translated, list):
        translated = ' '.join(str(part) for part in translated)
    translated = normalize_unicode_text(translated or '').strip()
    if not translated:
        raise RuntimeError('Lara returned an empty translation.')
    if translated.casefold() == text.strip().casefold():
        # Identity can be legitimate for names, but reject suspicious unchanged
        # output when source and target are different languages.
        if source != target and len(text.strip()) > 3:
            logger.warning('Lara returned unchanged text for %s -> %s', source, target)
    return translated


async def _translate_with_mymemory(text: str, source: str, target: str) -> str:
    """Optional legacy fallback; disabled unless explicitly enabled."""
    endpoint = os.getenv('MYMEMORY_API_URL', 'https://api.mymemory.translated.net/get').strip()
    params = {'q': text, 'langpair': f'{source}|{target}'}
    email = os.getenv('MYMEMORY_EMAIL', '').strip()
    if email:
        params['de'] = email
    async with httpx.AsyncClient(timeout=httpx.Timeout(5, connect=2)) as client:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
    translated = str(data.get('responseData', {}).get('translatedText', '')).strip()
    if not translated or translated.startswith('MYMEMORY WARNING'):
        raise RuntimeError('MyMemory did not return a valid translation.')
    return translated


async def translate_text(text: str, source_language: str, target_language: str) -> str:
    """Translate using exact phrase memory, then Lara; no fabricated fallback."""
    clean_text = normalize_unicode_text(text).strip()
    if not clean_text:
        raise RuntimeError('Text to translate is empty.')

    source = _lang(source_language)
    target = _lang(target_language)
    if source not in SUPPORTED_LANGUAGE_LOCALES or target not in SUPPORTED_LANGUAGE_LOCALES:
        raise RuntimeError(f'Unsupported translation pair: {source} -> {target}.')
    if _looks_like_corrupted_hindi(clean_text, source):
        raise RuntimeError('Hindi transcript appears corrupted before translation (question-mark placeholders). Check UTF-8 input and retry.')
    if source == target:
        return clean_text

    corpus_match = _lookup_corpus_translation(clean_text, source, target)
    if corpus_match:
        return corpus_match

    try:
        return await asyncio.to_thread(_translate_with_lara, clean_text, source, target)
    except Exception as lara_error:
        # MyMemory is an opt-in backup, not the primary translator.
        if os.getenv('TRANSLATION_FALLBACK', '').strip().lower() == 'mymemory':
            try:
                return await _translate_with_mymemory(clean_text, source, target)
            except Exception as fallback_error:
                logger.warning('Lara and MyMemory translation failed; error_types=%s,%s', type(lara_error).__name__, type(fallback_error).__name__)
                raise RuntimeError('Translation unavailable: Lara and MyMemory providers failed.') from fallback_error
        logger.warning('Lara translation failed; error_type=%s', type(lara_error).__name__)
        raise RuntimeError('Translation unavailable: Lara provider failed.') from lara_error


async def translate_chat_message(
    text: str,
    fallback_source: str = 'en',
    fallback_target: str = 'hi'
) -> tuple[str, str, str]:
    """Translate each chat message, determining direction by script & Hinglish detection."""
    clean_text = normalize_unicode_text(text).strip()
    if not clean_text:
        return "", fallback_source, fallback_target

    source_default = _lang(fallback_source)
    target_default = _lang(fallback_target)
    if source_default == target_default:
        target_default = 'hi' if source_default == 'en' else 'en'

    script_language = _detect_script_language(clean_text)
    if script_language == 'hi' and 'mr' in (source_default, target_default) and 'hi' not in (source_default, target_default):
        script_language = 'mr'

    is_hindi_english_pair = {source_default, target_default} == {'hi', 'en'}

    if script_language in (source_default, target_default):
        source = script_language
        target = target_default if source == source_default else source_default
    elif is_hindi_english_pair:
        source = _detect_chat_source(clean_text, fallback_source)
        target = target_default if source == source_default else source_default
    else:
        source, target = source_default, target_default

    # Sentence-level Hinglish check
    norm_hinglish = re.sub(r'[^a-z0-9]+', ' ', clean_text.lower()).strip()
    if norm_hinglish in _KNOWN_HINGLISH_SENTENCES and source == 'hi' and target == 'en':
        return _KNOWN_HINGLISH_SENTENCES[norm_hinglish], source, target

    translation_input = clean_text
    if source == 'hi' and not re.search(r'[\u0900-\u097F]', clean_text):
        translation_input = await _roman_hinglish_to_devanagari(clean_text)

    translated = await translate_text(translation_input, source, target)
    return translated, source, target


async def process_phrase_text(
    audio_bytes: bytes,
    mime_type: str,
    source_language: str,
    target_language: str
) -> tuple[str, str]:
    """Transcribe a recorded phrase with Gnani STT and translate it."""
    if not audio_bytes:
        raise RuntimeError("The recorded phrase was empty. Please record again.")
    if len(audio_bytes) > 8 * 1024 * 1024:
        raise RuntimeError("Phrase is too large (8 MB maximum).")

    original = await transcribe_with_gnani(audio_bytes, mime_type, source_language)
    translated = await translate_text(original, source_language, target_language)
    return original, translated
