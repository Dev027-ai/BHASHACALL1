# BhashaCall: Six-Language Gnani.ai Implementation Notes

## 1. Supported Languages & BCP-47 Locales

| Language | Code | STT Locale | TTS Locale | Default Timbre v2.5 Voice | Voice Env Variable |
|---|---|---|---|---|---|
| **Hindi** | `hi` | `hi-IN` | `hi-IN` | `Nalini` | `GNANI_TTS_VOICE_HI` |
| **English (India)** | `en` | `en-IN` | `en-IN` | `Kaveri` | `GNANI_TTS_VOICE_EN` |
| **Bengali** | `bn` | `bn-IN` | `bn-IN` | `Mehuli` | `GNANI_TTS_VOICE_BN` |
| **Tamil** | `ta` | `ta-IN` | `ta-IN` | `Kavin` | `GNANI_TTS_VOICE_TA` |
| **Telugu** | `te` | `te-IN` | `te-IN` | `Lavanya` | `GNANI_TTS_VOICE_TE` |
| **Marathi** | `mr` | `mr-IN` | `mr-IN` | `Asmita` | `GNANI_TTS_VOICE_MR` |

Source and target languages are completely independent. Each user can speak in one language and listen in another, or swap dynamically during calls.

---

## 2. Gnani.ai Models Used

### Speech-to-Text: Prisma v3.0
- Model identifier: `prisma-v3.0`
- Streaming endpoint: `wss://api.vachana.ai/stt/v3/stream`
- Streaming protocol: signed 16-bit PCM little-endian, mono, 16,000 Hz, 1,024-byte frames (512 samples = 32ms)
- SDK Client: `gnani.stt.GnaniSTTStreamClient` & `gnani.stt.GnaniSTTClient`
- Formats: `codemix` (for Hinglish & Hindi), `transcribe`, and `verbatim`
- Language Detection: `indic-auto` with candidate sets `['hi-IN', 'en-IN', 'bn-IN', 'ta-IN', 'te-IN', 'mr-IN']`

### Text-to-Speech: Timbre v2.5
- Model identifier: `timbre-v2.5`
- Streaming endpoint: `wss://api.vachana.ai/api/v1/tts`
- SDK Client: `gnani.tts.GnaniTTSRealtimeClient`
- Verified catalogue of 42 voices:
  *Ambuja, Asmita, Bhavna, Brinda, Chitra, Deepak, Devika, Dhruva, Falak, Girish, Hemraj, Ishaan, Jalaj, Jwala, Kaveri, Kavin, Kirra, Lavanya, Lehara, Mehuli, Nalini, Noopur, Omkar, Poorvi, Pranav, Reshma, Riyaan, Roopesh, Saanvi, Shlok, Suhana, Trisha, Trupti, Urmila, Varuni, Vedika, Veera, Vikrant, Yashvi, Yukti, Zahira, Zayan*
- Audio Config: `AudioConfig(sample_rate=48000, encoding='linear_pcm', container='wav', num_channels=1, sample_width=2)`

---

## 3. Real-Time Voice Flow

1. **Browser Capture**: Web Audio API captures microphone audio via `ScriptProcessorNode` at 16,000 Hz mono.
2. **PCM Packetization**: Audio frames are framed into 512 samples (1,024 bytes) corresponding to 32ms.
3. **Transport**: Frames are sent over the room WebSocket connection (`type: 'audio.stream_chunk'`).
4. **Gnani Prisma STT**: Backend streams frames to `GnaniSTTStreamClient`.
5. **Transcript Event**: Gnani yields `StreamTranscriptEvent` containing text and detected language metadata.
6. **Translation**: The transcript is translated into the other participant's selected target language.
7. **Gnani Timbre TTS**: `GnaniTTSRealtimeClient` synthesizes natural speech in the target language and voice.
8. **Delivery & Playback**: Audio chunks are delivered exclusively to the other participant (`exclude=sender`) preventing feedback loops.

---

## 4. Verification & Automated Test Status

- **33 Pytest Tests Passing** (`backend/tests/`):
  - All 12 specified bidirectional language pairs verified.
  - Prisma v3.0 STT & Timbre v2.5 TTS configuration and streaming verified.
  - Full two-participant full-duplex WebSocket conversation verified.
  - Audio conversion (16kHz mono WAV, 1024-byte frames) verified.
- **Frontend Production Build**: `tsc -b && vite build` passed in 4.26s.
- **Live Smoke Test Script**: `backend/test_gnani_live.py` ready for authenticated live testing with credit conservation.
