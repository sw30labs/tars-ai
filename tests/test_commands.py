"""Tests for the command registry: settings, persistence, character commands."""

import pytest

from config.settings import TARSConfig
from core.commands import (
    CommandRegistry,
    register_settings_commands,
    register_persistence_commands,
)
from core.character_commands import register_character_commands, _extract_names
from core.characters import resolve_character
from core.orchestrator import ConversationOrchestrator


@pytest.fixture
def config():
    return TARSConfig()


@pytest.fixture
def orchestrator(config):
    return ConversationOrchestrator(config, llm=None, tars_system_prompt="You are TARS.")


# ── Settings commands ────────────────────────────────────────────────────

def make_settings_registry():
    registry = CommandRegistry()
    ctx = {"rebuild_prompt": lambda: None}
    register_settings_commands(registry, ctx)
    return registry, ctx


def test_settings_query(config):
    registry, ctx = make_settings_registry()
    resp = registry.dispatch("what are your settings", config, ctx)
    assert resp is not None
    assert "HUMOR" in resp
    assert "75%" in resp
    assert "All systems nominal." in resp


def test_settings_adjust(config):
    registry, ctx = make_settings_registry()
    resp = registry.dispatch("set humor to 50", config, ctx)
    assert resp is not None
    assert config.personality.humor == 50


def test_settings_adjust_rejects_out_of_range(config):
    registry, ctx = make_settings_registry()
    resp = registry.dispatch("set honesty to 150", config, ctx)
    assert "0 to 100" in resp
    assert config.personality.honesty == 90


def test_unrelated_text_matches_nothing(config):
    registry, ctx = make_settings_registry()
    assert registry.dispatch("tell me about the mission", config, ctx) is None


# ── Persistence commands ─────────────────────────────────────────────────

def test_save_as_extracts_name(config):
    saved = []
    registry = CommandRegistry()
    ctx = {"save_conversation": lambda name: saved.append(name) or "ok"}
    register_persistence_commands(registry, ctx)

    assert registry.dispatch("save as my session", config, ctx) == "ok"
    assert saved == ["my session"]


def test_save_without_name(config):
    saved = []
    registry = CommandRegistry()
    ctx = {"save_conversation": lambda name: saved.append(name) or "ok"}
    register_persistence_commands(registry, ctx)

    registry.dispatch("save", config, ctx)
    assert saved == [None]


# ── Character commands ───────────────────────────────────────────────────

def make_character_registry(orchestrator):
    registry = CommandRegistry()
    ctx = {"orchestrator": orchestrator}
    register_character_commands(registry, ctx)
    return registry, ctx


def test_call_character(config, orchestrator):
    registry, ctx = make_character_registry(orchestrator)
    resp = registry.dispatch("call brand", config, ctx)
    assert "Brand has joined" in resp
    assert orchestrator._active_ids == ["tars", "brand"]


def test_call_multiple_characters(config, orchestrator):
    registry, ctx = make_character_registry(orchestrator)
    resp = registry.dispatch("call brand, also call dr mann and murph", config, ctx)
    assert "Brand has joined" in resp
    assert "Dr. Mann has joined" in resp
    assert "Murphy has joined" in resp
    assert orchestrator._active_ids == ["tars", "brand", "mann", "murphy"]


def test_call_everyone(config, orchestrator):
    registry, ctx = make_character_registry(orchestrator)
    registry.dispatch("call everyone", config, ctx)
    assert set(orchestrator._active_ids) == {
        "tars", "brand", "mann", "professor_brand", "murphy"
    }


def test_dismiss_character(config, orchestrator):
    orchestrator.call_character("mann")
    registry, ctx = make_character_registry(orchestrator)
    resp = registry.dispatch("dismiss dr mann", config, ctx)
    assert "Dr. Mann has left" in resp
    assert orchestrator._active_ids == ["tars"]


def test_get_is_not_a_call_verb(config, orchestrator):
    """'get me a status report' must not summon anyone."""
    registry, ctx = make_character_registry(orchestrator)
    assert registry.dispatch("get me a status report", config, ctx) is None
    assert orchestrator._active_ids == ["tars"]


def test_who_is_here(config, orchestrator):
    registry, ctx = make_character_registry(orchestrator)
    resp = registry.dispatch("who's here?", config, ctx)
    assert "TARS" in resp


# ── Name extraction & aliases ────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("call brand", ["brand"]),
    ("tars, call brand and mann", ["brand", "mann"]),
    ("call brand, mann, murphy", ["brand", "mann", "murphy"]),
    ("call brand, also call dr mann, also call murphy", ["brand", "dr mann", "murphy"]),
])
def test_extract_names(text, expected):
    verbs = r'(?:call|summon|bring in|wake up|invite)'
    assert _extract_names(text, verbs) == expected


@pytest.mark.parametrize("alias,expected_id", [
    ("brand", "brand"),
    ("amelia", "brand"),
    ("dr. mann", "mann"),
    ("professor", "professor_brand"),
    ("murph", "murphy"),
    ("tars", "tars"),
])
def test_resolve_character_aliases(alias, expected_id):
    assert resolve_character(alias).id == expected_id


def test_resolve_unknown_returns_none():
    assert resolve_character("ripley") is None
