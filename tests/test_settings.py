"""Tests for config/settings.py — validation and personality prompt blocks."""

import pytest

from config.settings import TARSConfig, TARSPersonality
from core.prompt import build_tars_system_prompt


def test_default_config_validates():
    TARSConfig().validate()


def test_validate_rejects_bad_url():
    config = TARSConfig()
    config.omlx.server_url = "127.0.0.1:8000/v1"
    with pytest.raises(ValueError, match="http"):
        config.validate()


def test_validate_rejects_nonpositive_values():
    config = TARSConfig()
    config.tts.speed = 0
    with pytest.raises(ValueError, match="speed"):
        config.validate()

    config = TARSConfig()
    config.conversation_memory_k = 0
    with pytest.raises(ValueError, match="conversation_memory_k"):
        config.validate()


def test_personality_range_enforced():
    with pytest.raises(ValueError):
        TARSPersonality(humor=101)
    with pytest.raises(ValueError):
        TARSPersonality(trust=-1)


def test_personality_prompt_block_scales():
    high = TARSPersonality(humor=95).to_prompt_block()
    low = TARSPersonality(humor=10).to_prompt_block()
    assert "HIGH" in high
    assert "DISABLED" in low


def test_system_prompt_injects_personality():
    prompt = build_tars_system_prompt(TARSPersonality(humor=75, honesty=90))
    assert "Humor: 75%" in prompt
    assert "Honesty: 90%" in prompt
