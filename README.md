# BhashaCall — Real-Time Multilingual Voice Communication Powered by Gnani.ai

> **"Speak in your own language. Let the other person hear you in theirs."**

Built for the **Gnani.ai Great Indian AI Internship Challenge & Hackathon**, **BhashaCall** enables natural, bidirectional, real-time voice conversations across Indian languages. Person A speaks naturally in Hindi, Gnani Prisma v3.0 recognizes the speech, it is translated into Tamil, and Gnani Timbre v2.5 synthesizes natural Tamil voice output for Person B. When Person B responds in Tamil, Person A hears natural Hindi voice output.

---

## 1. Hackathon Objective & The Problem

In a diverse multilingual nation like India with 22 scheduled languages and hundreds of dialects, language barriers create friction in healthcare, commerce, education, and daily life. Most existing solutions either:
1. Force users to type translated text messages back and forth.
2. Require unnatural pause-and-play phrase buttons.
3. Rely on generic foreign speech engines that fail on Indian accents, native phonetics, and Hinglish.

### The BhashaCall Solution
BhashaCall solves this by creating a true real-time voice calling experience powered natively by **Gnani.ai's state-of-the-art speech intelligence models**:
- **Gnani Prisma v3.0**: Real-time multilingual Speech-to-Text with native Indian phonetics, `indic-auto` language detection, and Hinglish codemix understanding.
- **Gnani Timbre v2.5**: Low-latency, streaming Text-to-Speech across 42 verified voices with native Indian intonation and cadence.
- **Independent Full-Duplex Language Selection**: Each participant independently selects their speaking language and hearing language.
- **Real Audio Transport & Echo Suppression**: Translated voice is synthesized and played directly to the recipient without audio feedback loops.

---

## 2. System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    BHASHACALL ARCHITECTURE                              |
+-----------------------------------------------------------------------------------------+
                                                                                         
 [ Browser Client A ]                                              [ Browser Client B ] 
 (Speaker: Hindi)                                                  (Speaker: Tamil)     
        |                                                                 ^             
        | 1. Web Audio API captures 16kHz PCM frames (32ms / 1024 bytes)  | 6. Plays    
        v                                                                 |    Tamil WAV
+-------------------------------------------------------------------------+-------------+
|                                    BACKEND (FastAPI)                                  |
|                                                                                       |
|   +-----------------------+     +--------------------+     +----------------------+   |
|   |  WebSocket Room Hub   |     | Translation Engine |     |   Audio Stream Hub   |   |
|   |  /ws/{code}/{user_id} |     | (6 Language Pairs  |     |  Frame Buffer & VAD  |   |
|   |                       |     |  + Hinglish)       |     |                      |   |
|   +-----------+-----------+     +---------+----------+     +----------+-----------+   |
|               |                           ^                           ^               |
+---------------+---------------------------+---------------------------+---------------+
                |                           |                           |               
                | 2. Streams PCM frames     | 4. Translated text        | 5. Synthesized
                v                           |                            |    audio      
   +----------------------------+           |               +-----------+-------------+ 
   |   Gnani Prisma v3.0 STT    |           |               |   Gnani Timbre v2.5 TTS | 
   |   wss://api.vachana.ai/    |-----------+               |   wss://api.vachana.ai/ | 
   |   stt/v3/stream            | 3. Transcript Event       |   api/v1/tts            | 
   |   (indic-auto / codemix)   |    (hi-IN detected)       |   (Tamil Voice: Kavin)  | 
   +----------------------------+                           +-------------------------+ 
```

---

## 3. Technology Stack

- **Speech Intelligence**: Official `gnani-vachana` Python SDK (`v0.9.0`)
  - STT Model: `prisma-v3.0` (`GnaniSTTStreamClient`, `GnaniSTTClient`)
  - TTS Model: `timbre-v2.5` (`GnaniTTSRealtimeClient`, `AudioConfig`)
- **Backend**: FastAPI, WebSockets, Python 3.11+, PyAV (`av`), NumPy, PyMuPDF, SQLite
- **Frontend**: React 18, TypeScript 5.6, Vite 6, Web Audio API (ScriptProcessor 16kHz mono), Lucide Icons
- **Signaling & Calling**: WebSockets & WebRTC peer-to-peer call lifecycle coordination

---

## 4. Supported Languages & Verified Voice Catalogue

BhashaCall supports 6 major Indian languages across STT, Translation, TTS, Live Captions, Room Chat, and Document Audio:

| Language | BCP-47 Locale | STT Model | Default Verified Voice | Voice Environment Variable |
|---|---|---|---|---|
| **Hindi** | `hi-IN` | `prisma-v3.0` | `Nalini` | `GNANI_TTS_VOICE_HI` |
| **English (India)** | `en-IN` | `prisma-v3.0` | `Kaveri` | `GNANI_TTS_VOICE_EN` |
| **Bengali** | `bn-IN` | `prisma-v3.0` | `Mehuli` | `GNANI_TTS_VOICE_BN` |
| **Tamil** | `ta-IN` | `prisma-v3.0` | `Kavin` | `GNANI_TTS_VOICE_TA` |
| **Telugu** | `te-IN` | `prisma-v3.0` | `Lavanya` | `GNANI_TTS_VOICE_TE` |
| **Marathi** | `mr-IN` | `prisma-v3.0` | `Asmita` | `GNANI_TTS_VOICE_MR` |

All voices are validated against the 42 verified voices in the Gnani Timbre v2.5 catalogue:
*Ambuja, Asmita, Bhavna, Brinda, Chitra, Deepak, Devika, Dhruva, Falak, Girish, Hemraj, Ishaan, Jalaj, Jwala, Kaveri, Kavin, Kirra, Lavanya, Lehara, Mehuli, Nalini, Noopur, Omkar, Poorvi, Pranav, Reshma, Riyaan, Roopesh, Saanvi, Shlok, Suhana, Trisha, Trupti, Urmila, Varuni, Vedika, Veera, Vikrant, Yashvi, Yukti, Zahira, Zayan.*

---

## 5. Quickstart & Installation

### Prerequisites
- Python 3.11+
- Node.js v18+ and npm

### 1. Backend Setup
```powershell
cd backend

# Create virtual environment (if not already created)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install requirements (includes gnani-vachana, fastapi, uvicorn, av, websockets)
pip install -r requirements.txt

# Configure environment variables
Copy-Item .env.example .env
# Edit .env and insert your GNANI_API_KEY
```

### 2. Frontend Setup
```powershell
cd frontend
npm install
npm run build   # Verifies TypeScript compilation and creates production build
npm run dev     # Starts Vite dev server on http://localhost:5173
```

### 3. Run Backend Server
```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Verify backend health at `http://localhost:8000/api/health`.

---

## 6. How to Test a Two-Person Voice Call

1. Open `http://localhost:5173` in **Browser Window A** (e.g. Chrome).
2. Click **Start a voice room** -> **Create new room**. Note the generated Room Code (e.g. `ABC1234`).
3. Set Window A language direction:
   - **Speak in**: `Hindi`
   - **Translate to**: `Tamil`
4. Open an **Incognito / Second Browser Window B** (e.g. Edge or Chrome Incognito) at `http://localhost:5173`.
5. Enter the Room Code and click **Join room**.
6. Set Window B language direction:
   - **Speak in**: `Tamil`
   - **Translate to**: `Hindi`
7. Click **Start live call** in Window A. Window B will show an incoming call prompt. Click **Accept**.
8. Speak in Hindi in Window A:
   - Window A shows live caption: `[Prisma v3.0 (hi-IN)] नमस्ते, आप कैसे हैं?`
   - Window B automatically receives the translated Tamil caption and **plays the natural Tamil voice via Gnani Timbre v2.5**!
9. Speak in Tamil in Window B:
   - Window B shows live caption in Tamil.
   - Window A receives translated Hindi caption and **hears the synthesized Hindi voice output**!

---

## 7. Running the Automated Test Suite

A complete test suite covering all components is provided in `backend/tests/`:

```powershell
cd backend
python -m pytest -v tests/
```

### Test Coverage (33 Passing Tests)
- **`test_six_languages.py`**: All 12 specified bidirectional language pairs (Hindi↔English, Bengali↔English, Tamil↔English, Telugu↔English, Marathi↔English, Hindi↔Tamil), 6-language BCP-47 locales, verified voice mappings, and Hinglish chat translation.
- **`test_gnani_stt.py`**: Prisma v3.0 model configuration, explicit language selection, `indic-auto` language detection, real-time PCM chunk streaming, empty audio handling, and authentication error handling.
- **`test_gnani_tts.py`**: Timbre v2.5 model verification, 42-voice catalogue validation, unsupported voice error handling, audio format verification (48kHz WAV linear PCM), and streaming audio chunk delivery.
- **`test_audio_conversion.py`**: Signed 16-bit mono 16kHz PCM audio resampling and exact 1,024-byte (512 samples / 32ms) frame size compliance.
- **`test_api_routes.py`**: `/api/health`, `/api/rooms`, `/api/messages/translate`, and `/api/documents/ocr-capabilities`.
- **`test_conversation_flow.py`**: End-to-end full duplex WebSocket conversation simulating two participants speaking Hindi and Tamil with real-time speech synthesis and caption delivery.

### Minimal Authenticated Live Smoke Test (Credit Conserving)
To verify live authenticated connectivity with minimal Gnani credit consumption:
```powershell
cd backend
python test_gnani_live.py
```

---

## 8. Current Limitations & Future Improvements

- **Acoustic Feedback**: When testing two browser windows on the same physical machine without headphones, acoustic echo can occur. The frontend uses `echoCancellation: true`, but headphones are recommended for single-machine dual testing.
- **Network Relays**: WebRTC uses public STUN servers for peer signaling. Restrictive corporate firewalls may require a dedicated TURN relay.
- **Future Improvements**:
  - Integration with Gnani Live API for continuous bidirectional multi-turn dialogue.
  - Native Android/iOS client wrappers for mobile calling.
  - Speaker identification and voice profile preservation.

---

## 9. License & Credits

Built for the **Gnani.ai Great Indian AI Internship Hackathon**.
Speech recognition and synthesis powered by **Gnani.ai** (`prisma-v3.0` & `timbre-v2.5`).
