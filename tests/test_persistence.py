"""Tests for core/persistence.py — save/load roundtrip and name sanitization."""

import pytest

from langchain_core.messages import HumanMessage, AIMessage

from core import persistence


@pytest.fixture
def conv_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "CONVERSATIONS_DIR", tmp_path)
    return tmp_path


PERSONALITY = {"humor": 75, "honesty": 90, "discretion": 85, "trust": 70}


def test_save_load_roundtrip(conv_dir):
    msgs = [
        HumanMessage(content="hey tars", name="Cooper"),
        AIMessage(content="Cooper.", name="tars"),
    ]
    persistence.save_conversation(
        name="my session",
        messages=msgs,
        personality=PERSONALITY,
        context_summary="a summary",
        active_characters=["tars", "brand"],
    )

    data = persistence.load_conversation("my session")
    assert data is not None
    assert data["message_count"] == 2
    assert data["context_summary"] == "a summary"
    assert data["personality"] == PERSONALITY
    assert data["active_characters"] == ["tars", "brand"]
    assert data["messages"][0].content == "hey tars"
    assert data["messages"][0].name == "Cooper"
    assert data["messages"][1].content == "Cooper."
    assert data["messages"][1].name == "tars"


def test_load_missing_returns_none(conv_dir):
    assert persistence.load_conversation("nope") is None


@pytest.mark.parametrize("bad", ["../../etc/passwd", "..", "a/b", "a\\b", "x.json", ""])
def test_save_rejects_unsafe_names(conv_dir, bad):
    with pytest.raises(ValueError):
        persistence.save_conversation(bad, [], PERSONALITY)


@pytest.mark.parametrize("bad", ["../../etc/passwd", "..", "a/b", "a\\b", ""])
def test_load_rejects_unsafe_names(conv_dir, bad):
    assert persistence.load_conversation(bad) is None


def test_list_conversations(conv_dir):
    persistence.save_conversation("one", [], PERSONALITY)
    persistence.save_conversation("two", [HumanMessage(content="hi")], PERSONALITY)
    sessions = persistence.list_conversations()
    names = [s["name"] for s in sessions]
    assert names == ["one", "two"]
    assert sessions[1]["message_count"] == 1
