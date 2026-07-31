"""Tests for ui.py — parameter bars, tags, mission clock."""

import re

import ui
from config.settings import TARSPersonality
from core.characters import CHARACTER_REGISTRY


def strip_markup(text: str) -> str:
    return re.sub(r"\[/?[^\[\]]*\]", "", text)


def test_parameter_bar_proportions():
    bar = ui.parameter_bar(75, width=20)
    assert bar.count("█") == 15
    assert bar.count("░") == 5


def test_parameter_bar_clamps_out_of_range():
    assert ui.parameter_bar(150, width=10).count("█") == 10
    assert ui.parameter_bar(-5, width=10).count("░") == 10


def test_parameter_display_contains_all_knobs():
    text = strip_markup(ui.parameter_display(TARSPersonality()))
    for knob in ("HUMOR", "HONESTY", "DISCRETION", "TRUST"):
        assert knob in text
    assert "All systems nominal." in text


def test_name_tag_uses_character_style_and_uppercase():
    tag = ui.name_tag(CHARACTER_REGISTRY["mann"])
    assert "bold yellow" in tag
    assert "DR. MANN" in tag


def test_mission_elapsed_format():
    assert re.fullmatch(r"T\+\d{2}:\d{2}:\d{2}", ui.mission_elapsed())


def test_alert_tolerates_brackets_in_message():
    # Dynamic text (exception messages, user input) must not break markup parsing.
    ui.alert("OMLX is down [/] connection failed [500]")
    ui.say_tars("I don't recognize '[x]'.")
    ui.warn("weird [input")


def test_unknown_character_with_brackets_does_not_crash():
    from config.settings import TARSConfig
    from core.commands import CommandRegistry
    from core.character_commands import register_character_commands
    from core.orchestrator import ConversationOrchestrator

    orch = ConversationOrchestrator(TARSConfig(), llm=None, tars_system_prompt="x")
    registry = CommandRegistry()
    ctx = {"orchestrator": orch}
    register_character_commands(registry, ctx)
    resp = registry.dispatch("call [/] weird", TARSConfig(), ctx)
    assert resp is not None  # escaped echo, no MarkupError
