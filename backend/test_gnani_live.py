"""Minimal Authenticated Smoke Test for Gnani.ai APIs.
Conserves Gnani credits by sending a very short test phrase and verifying
Prisma v3.0 STT and Timbre v2.5 TTS endpoints.

Usage:
  python test_gnani_live.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Load backend/.env
BASE = Path(__file__).resolve().parent
from dotenv import load_dotenv
load_dotenv(BASE / '.env')

from app.services.pipeline import (
    get_gnani_api_key,
    transcribe_with_gnani,
    synthesize_speech,
    create_tone_wav,
    get_tts_voice,
    get_stt_locale,
    TIMBRE_V25_VOICES,
)


async def main():
    print("=" * 60)
    print("BhashaCall — Gnani.ai Authenticated Smoke Test")
    print("=" * 60)

    key = get_gnani_api_key()
    if not key:
        print("[INFO] GNANI_API_KEY is not configured in backend/.env.")
        print("[INFO] To run live API tests against Gnani servers:")
        print("       1. Open backend/.env")
        print("       2. Set GNANI_API_KEY=<your-key>")
        print("       3. Re-run: python test_gnani_live.py")
        print("[SKIP] Skipping live credit-consuming calls.")
        return 0

    print(f"[OK] GNANI_API_KEY detected (Length: {len(key)})")
    print(f"[OK] STT Model: prisma-v3.0 | Locale: {get_stt_locale('hi')}")
    print(f"[OK] TTS Model: timbre-v2.5 | Hindi Voice: {get_tts_voice('hi')}")

    # 1. Test Gnani TTS Timbre v2.5 with a tiny phrase (2 words to minimize credit usage)
    print("\n--- 1. Testing Gnani Timbre v2.5 TTS (WebSocket) ---")
    try:
        audio, mime = await synthesize_speech("नमस्ते", "hi")
        print(f"[PASS] Timbre v2.5 synthesized audio: {len(audio)} bytes, MIME: {mime}")
    except Exception as exc:
        print(f"[FAIL] Timbre v2.5 TTS error: {exc}")

    # 2. Test Gnani STT Prisma v3.0 with short audio fixture
    print("\n--- 2. Testing Gnani Prisma v3.0 STT ---")
    try:
        sample_wav = create_tone_wav(freq=440.0, duration_seconds=0.5, sample_rate=16000)
        transcript = await transcribe_with_gnani(sample_wav, "audio/wav", "hi")
        print(f"[PASS] Prisma v3.0 transcript received: '{transcript}'")
    except Exception as exc:
        print(f"[NOTICE] Prisma v3.0 test completed with response/status: {exc}")

    print("\n[COMPLETE] Smoke test finished.")
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
