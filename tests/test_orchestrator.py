"""Tests for core/orchestrator.py — silence detection, role mapping, rounds."""

import pytest

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config.settings import TARSConfig
from core.characters import CHARACTER_REGISTRY
from core.orchestrator import ConversationOrchestrator


class FakeLLM:
    """Returns canned replies, recording the max_tokens each call received."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.max_tokens_seen = []

    def generate(self, messages, on_token=None, max_tokens=None):
        self.max_tokens_seen.append(max_tokens)
        text = self.replies.pop(0)
        if on_token:
            # One big chunk exercises the buffered silence detection.
            on_token(text)
        return text


class BoomLLM:
    def generate(self, messages, on_token=None, max_tokens=None):
        raise RuntimeError("OMLX is down")


@pytest.fixture
def config():
    return TARSConfig()


def make_orchestrator(config, llm):
    return ConversationOrchestrator(config, llm, tars_system_prompt="You are TARS.")


# ── Silence detection ────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["[SILENT]", "[silent]", "[ silent ]", "[silent].", "silent"])
def test_is_silent(config, text):
    orch = make_orchestrator(config, FakeLLM([]))
    assert orch._is_silent(text)


@pytest.mark.parametrize("text", ["Affirmative.", "[SILENT] wait no, I have thoughts"])
def test_is_not_silent(config, text):
    orch = make_orchestrator(config, FakeLLM([]))
    assert not orch._is_silent(text)


# ── Role mapping ─────────────────────────────────────────────────────────

def test_map_message_role_own_and_other(config):
    orch = make_orchestrator(config, FakeLLM([]))
    tars = CHARACTER_REGISTRY["tars"]
    brand = CHARACTER_REGISTRY["brand"]

    own = AIMessage(content="Affirmative.", name="tars")
    assert isinstance(orch._map_message_role(own, tars), AIMessage)

    other = orch._map_message_role(own, brand)
    assert isinstance(other, HumanMessage)
    assert other.content == "TARS: Affirmative."


def test_map_message_role_cooper_prefix_with_guests(config):
    orch = make_orchestrator(config, FakeLLM([]))
    tars = CHARACTER_REGISTRY["tars"]
    msg = HumanMessage(content="status?", name="Cooper")

    solo = orch._map_message_role(msg, tars)
    assert solo.content == "status?"

    orch.call_character("brand")
    grouped = orch._map_message_role(msg, tars)
    assert grouped.content == "Cooper: status?"


# ── Round generation ─────────────────────────────────────────────────────

def test_single_character_round(config):
    orch = make_orchestrator(config, FakeLLM(["Affirmative, Cooper."]))
    responses = orch.generate_round("status report")

    assert len(responses) == 1
    assert responses[0].text == "Affirmative, Cooper."
    assert not responses[0].silent
    # History: user message + TARS reply
    assert len(orch.messages) == 2
    assert isinstance(orch.messages[0], HumanMessage)
    assert isinstance(orch.messages[1], AIMessage)
    assert orch.messages[1].name == "tars"


def test_silent_guest_not_committed(config):
    orch = make_orchestrator(config, FakeLLM(["Cooper.", "[SILENT]"]))
    orch.call_character("brand")

    responses = orch.generate_round("tars, status?")

    assert responses[1].silent
    # Only TARS's reply is in history
    assert len(orch.messages) == 2
    assert all(getattr(m, "name", None) != "brand" for m in orch.messages)


def test_guest_max_tokens_capped(config):
    llm = FakeLLM(["Cooper.", "Indeed."])
    orch = make_orchestrator(config, llm)
    orch.call_character("brand")
    orch.generate_round("hello")

    tars_tokens, brand_tokens = llm.max_tokens_seen
    assert tars_tokens == CHARACTER_REGISTRY["tars"].max_tokens
    assert brand_tokens == config.multi_character_max_tokens


def test_followup_when_addressed_with_question(config):
    llm = FakeLLM([
        "Brand, what is your read on this?",  # TARS main turn
        "I agree with the plan.",             # Brand main turn
        "The data supports it.",              # Brand follow-up turn
    ])
    orch = make_orchestrator(config, llm)
    orch.call_character("brand")

    responses = orch.generate_round("let's decide")

    assert len(responses) == 3
    assert responses[2].character.id == "brand"
    assert responses[2].text == "The data supports it."


def test_failed_round_rolls_back_history(config):
    orch = make_orchestrator(config, BoomLLM())

    with pytest.raises(RuntimeError):
        orch.generate_round("status report")

    assert orch.messages == []


def test_failed_round_rolls_back_partial_commits(config):
    """TARS answers, then Brand blows up mid-scene: nothing is kept."""
    class PartialLLM:
        def __init__(self):
            self.calls = 0

        def generate(self, messages, on_token=None, max_tokens=None):
            self.calls += 1
            if self.calls == 1:
                if on_token:
                    on_token("Cooper.")
                return "Cooper."
            raise RuntimeError("OMLX died mid-round")

    orch = make_orchestrator(config, PartialLLM())
    orch.call_character("brand")

    with pytest.raises(RuntimeError):
        orch.generate_round("status report")

    assert orch.messages == []


def test_reset_clears_everything(config):
    orch = make_orchestrator(config, FakeLLM(["Hi.", "[SILENT]"]))
    orch.call_character("brand")
    orch.generate_round("hello")
    orch.reset()

    assert orch.messages == []
    assert orch.context_summary == ""
    assert orch._active_ids == ["tars"]
