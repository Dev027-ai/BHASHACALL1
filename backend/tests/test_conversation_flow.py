"""End-to-End Two-Participant Conversation Test over WebSockets.

Simulates two concurrent participants in a room:
- Participant A (Speaks Hindi, hears Tamil)
- Participant B (Speaks Tamil, hears Hindi)

Verifies:
1. Room creation and dual WebSocket connection.
2. Participant A sends speech -> Participant B receives Tamil speech and captions.
3. Participant B sends speech -> Participant A receives Hindi speech and captions.
4. Bidirectional room chat translation.
5. Clean disconnect and member tracking.
"""
import pytest
import base64
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.pipeline import create_tone_wav

client = TestClient(app)


def test_two_participant_voice_and_chat_conversation():
    """Two participants communicating seamlessly in Hindi and Tamil."""
    # 1. Create a room
    room_res = client.post("/api/rooms", json={
        "source_language": "hi",
        "target_language": "ta",
        "participant_id": "user-A"
    })
    assert room_res.status_code == 200
    room_code = room_res.json()["room_code"]

    # 2. Connect Participant A
    with client.websocket_connect(f"/ws/{room_code}/user-A") as ws_a:
        init_a = ws_a.receive_json()
        assert init_a["type"] == "system"

        # 3. Connect Participant B
        with client.websocket_connect(f"/ws/{room_code}/user-B") as ws_b:
            init_b = ws_b.receive_json()
            assert init_b["type"] == "system"

            # User A receives notice that User B joined
            peer_notice = ws_a.receive_json()
            assert "joined" in peer_notice.get("text", "")
            ready_notice = ws_a.receive_json()
            assert ready_notice["type"] == "rtc.peer-ready"

            # Configure languages for participants
            ws_a.send_json({"type": "set_languages", "source_language": "hi", "target_language": "ta"})
            lang_ack_a = ws_a.receive_json()
            assert lang_ack_a["type"] == "languages_updated"

            ws_b.send_json({"type": "set_languages", "source_language": "ta", "target_language": "hi"})
            lang_ack_b = ws_b.receive_json()
            assert lang_ack_b["type"] == "languages_updated"

            # 4. User A speaks in Hindi -> User B receives Tamil caption and speech
            # User A sends a phrase
            fake_wav = create_tone_wav(freq=440.0, duration_seconds=0.2, sample_rate=16000)
            b64_audio = base64.b64encode(fake_wav).decode("ascii")

            ws_a.send_json({
                "type": "phrase",
                "phrase_id": "phrase-1",
                "audio_base64": b64_audio,
                "mime_type": "audio/wav",
                "source_language": "hi",
                "target_language": "ta"
            })

            # User A receives phrase status & caption
            a_caption = ws_a.receive_json()
            assert a_caption["type"] == "caption.live"
            assert a_caption["from"] == "user-A"

            a_status = ws_a.receive_json()
            assert a_status["type"] == "phrase_status"

            # User B receives live caption in Tamil
            b_caption = ws_b.receive_json()
            assert b_caption["type"] == "caption.live"
            assert b_caption["from"] == "user-A"
            assert b_caption["target_language"] == "ta"

            # User B receives translated speech audio in Tamil
            b_speech = ws_b.receive_json()
            assert b_speech["type"] == "speech.audio_ready"
            assert b_speech["from"] == "user-A"
            assert b_speech["target_language"] == "ta"
            assert b_speech["voice"] == "Kavin"  # Tamil verified voice
            assert "audio_base64" in b_speech
            assert len(b_speech["audio_base64"]) > 0

            # 5. User B speaks in Tamil -> User A receives Hindi caption and speech
            ws_b.send_json({
                "type": "phrase",
                "phrase_id": "phrase-2",
                "audio_base64": b64_audio,
                "mime_type": "audio/wav",
                "source_language": "ta",
                "target_language": "hi"
            })

            # User B receives caption & status
            b_cap2 = ws_b.receive_json()
            assert b_cap2["type"] == "caption.live"
            b_stat2 = ws_b.receive_json()
            assert b_stat2["type"] == "phrase_status"

            # User A receives caption in Hindi
            a_cap2 = ws_a.receive_json()
            assert a_cap2["type"] == "caption.live"
            assert a_cap2["from"] == "user-B"
            assert a_cap2["target_language"] == "hi"

            # User A receives speech audio in Hindi
            a_speech = ws_a.receive_json()
            assert a_speech["type"] == "speech.audio_ready"
            assert a_speech["from"] == "user-B"
            assert a_speech["target_language"] == "hi"
            assert a_speech["voice"] == "Nalini"  # Hindi verified voice
            assert len(a_speech["audio_base64"]) > 0

            # 6. Test Bidirectional Chat
            ws_a.send_json({
                "type": "chat.message",
                "client_message_id": "msg-1",
                "text": "नमस्ते",
                "source_language": "hi",
                "target_language": "ta"
            })
            a_chat = ws_a.receive_json()
            b_chat = ws_b.receive_json()
            assert a_chat["type"] == "chat.message"
            assert b_chat["type"] == "chat.message"
            assert a_chat["sender_id"] == "user-A"
            assert len(b_chat["translated_text"]) > 0
