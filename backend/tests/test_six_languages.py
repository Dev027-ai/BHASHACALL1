"""Tests for Six-Language Support across all 12 specified language pairs:
1. Hindi -> English
2. English -> Hindi
3. Bengali -> English
4. English -> Bengali
5. Tamil -> English
6. English -> Tamil
7. Telugu -> English
8. English -> Telugu
9. Marathi -> English
10. English -> Marathi
11. Hindi -> Tamil
12. Tamil -> Hindi
"""
import pytest
import asyncio
from app.services.pipeline import (
    translate_text,
    translate_chat_message,
    get_stt_locale,
    get_tts_locale,
    get_tts_voice,
    SUPPORTED_LANGUAGE_LOCALES,
    DEFAULT_VOICE_MAP,
    TIMBRE_V25_VOICES,
)


@pytest.mark.parametrize("source,target,phrase,expected_substr", [
    ('hi', 'en', 'नमस्ते', 'hello'),
    ('en', 'hi', 'Hello', 'नमस्ते'),
    ('bn', 'en', 'নমস্কার', 'hello'),
    ('en', 'bn', 'Hello', 'নমস্কার'),
    ('ta', 'en', 'வணக்கம்', 'hello'),
    ('en', 'ta', 'Hello', 'வணக்கம்'),
    ('te', 'en', 'నమస్కారం', 'hello'),
    ('en', 'te', 'Hello', 'నమస్కారం'),
    ('mr', 'en', 'नमस्कार', 'hello'),
    ('en', 'mr', 'Hello', 'नमस्कार'),
    ('hi', 'ta', 'नमस्ते', 'வணக்கம்'),
    ('ta', 'hi', 'வணக்கம்', 'नमस्ते'),
])
def test_twelve_specified_language_pairs(source, target, phrase, expected_substr):
    """Verify bidirectional translation between all 12 specified language pairs."""
    result = asyncio.run(translate_text(phrase, source, target))
    assert result is not None
    assert len(result.strip()) > 0
    assert expected_substr.lower() in result.lower()


def test_six_language_locales_and_voices():
    """Verify BCP-47 locales and voice configuration for all 6 languages."""
    languages = ['hi', 'en', 'bn', 'ta', 'te', 'mr']

    for lang in languages:
        stt_locale = get_stt_locale(lang)
        tts_locale = get_tts_locale(lang)
        voice = get_tts_voice(lang)

        # Locale must be a valid BCP-47 format with -IN
        assert stt_locale.endswith('-IN')
        assert tts_locale.endswith('-IN')
        assert stt_locale == SUPPORTED_LANGUAGE_LOCALES[lang]

        # Voice must be in the verified 42-voice catalogue
        assert voice in TIMBRE_V25_VOICES
        assert voice == DEFAULT_VOICE_MAP[lang]


def test_hinglish_chat_translation():
    """Verify Hinglish sentence understanding and translation into English."""
    hinglish_samples = [
        ("kyu tumhe aesa kyu lagta hai", "Why do you think so?"),
        ("yaar mujhe kal office jaana hai", "Friend, I have to go to office tomorrow."),
        ("can you please mujhe call karna", "Can you please call me?"),
    ]

    for utterance, expected_en in hinglish_samples:
        translated, src, tgt = asyncio.run(
            translate_chat_message(utterance, fallback_source='en', fallback_target='hi')
        )
        assert src == 'hi'
        assert tgt == 'en'
        assert expected_en.lower() in translated.lower()
