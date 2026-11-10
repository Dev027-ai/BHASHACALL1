"""Tests for FastAPI HTTP API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify health endpoint returns speech provider information and supported models."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "bhashacall-api"
    assert data["speech_provider"] == "gnani"
    assert data["stt_model"] == "prisma-v3.0"
    assert data["tts_model"] == "timbre-v2.5"
    assert "supported_languages" in data
    assert len(data["supported_languages"]) == 6
    assert data["voice_catalogue_count"] == 42


def test_create_and_query_room():
    """Verify room creation and room retrieval."""
    payload = {
        "source_language": "hi",
        "target_language": "ta",
        "participant_id": "test-user-1"
    }
    create_res = client.post("/api/rooms", json=payload)
    assert create_res.status_code == 200
    room_data = create_res.json()
    code = room_data["room_code"]
    assert len(code) > 0
    assert room_data["source_language"] == "hi"
    assert room_data["target_language"] == "ta"

    # Query room info
    info_res = client.get(f"/api/rooms/{code}")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["room_code"] == code
    assert info_data["source_language"] == "hi"
    assert info_data["target_language"] == "ta"


def test_standalone_message_translation():
    """Verify standalone translation API route."""
    payload = {
        "text": "Hello",
        "source_language": "en",
        "target_language": "hi",
        "sender_id": "test-user"
    }
    res = client.post("/api/messages/translate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "translated_text" in data
    assert len(data["translated_text"]) > 0


def test_ocr_capabilities_route():
    """Verify OCR capabilities endpoint returns structure."""
    res = client.get("/api/documents/ocr-capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "available" in data
    assert "engine" in data
