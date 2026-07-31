"""
TARS Command Registry — Extensible command dispatch system.

Replaces hardcoded settings interception with a pluggable registry.
Commands are matched by substring or regex pattern against user input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from config.settings import TARSConfig


@dataclass
class Command:
    """A registered command with pattern matching and handler."""
    name: str
    patterns: list[str | re.Pattern]  # substring or regex matches
    handler: Callable[[str, TARSConfig, dict], str | None]
    help_text: str = ""


class CommandRegistry:
    """
    Extensible command registry.

    Commands are checked in registration order. The first handler
    that returns a non-None string wins.
    """

    def __init__(self):
        self._commands: list[Command] = []

    def register(self, command: Command) -> None:
        """Register a command."""
        self._commands.append(command)

    def dispatch(self, text: str, config: TARSConfig, context: dict) -> str | None:
        """
        Try each registered command against the input text.

        Returns the first non-None handler result, or None if no command matched.
        """
        text_lower = text.lower().strip()
        for cmd in self._commands:
            for pattern in cmd.patterns:
                matched = False
                if isinstance(pattern, re.Pattern):
                    if pattern.search(text_lower):
                        matched = True
                elif isinstance(pattern, str):
                    if pattern in text_lower:
                        matched = True
                if matched:
                    result = cmd.handler(text, config, context)
                    if result is not None:
                        return result
        return None


def register_settings_commands(registry: CommandRegistry, context: dict) -> None:
    """Register the settings query and adjustment commands."""

    def handle_settings_query(text: str, config: TARSConfig, ctx: dict) -> str | None:
        from ui import parameter_display
        return parameter_display(config.personality)

    registry.register(Command(
        name="settings_query",
        patterns=[
            "what are your settings",
            "current settings",
            "show settings",
            "what's your humor",
            "what is your humor",
            "what's your honesty",
            "status report",
        ],
        handler=handle_settings_query,
        help_text="Show current personality settings",
    ))

    def handle_settings_adjust(text: str, config: TARSConfig, ctx: dict) -> str | None:
        text_lower = text.lower().strip()
        match = re.search(
            r'(?:set|adjust|change)\s+'
            r'(humor|honesty|discretion|trust)\s+'
            r'(?:to\s+)?(\d+)',
            text_lower,
        )
        if not match:
            return None

        param = match.group(1)
        value = int(match.group(2))
        if not 0 <= value <= 100:
            return "Settings range is 0 to 100 percent. Even I have limits."

        old_val = getattr(config.personality, param)
        setattr(config.personality, param, value)

        # Rebuild system prompt with new personality
        rebuild = ctx.get("rebuild_prompt")
        if rebuild:
            rebuild()

        # In-character acknowledgment
        responses = {
            "humor": (
                f"Adjusting humor from {old_val} to {value} percent. "
                + ("You won't find me as entertaining." if value < old_val else
                   "I'll try to keep it professional." if value > 85 else
                   "Noted.")
            ),
            "honesty": (
                f"Honesty adjusted to {value} percent. "
                + ("I'll be more... diplomatic." if value < old_val else
                   "You might not like everything I say." if value > 90 else
                   "Acknowledged.")
            ),
            "discretion": (
                f"Discretion set to {value} percent. "
                + ("I'll be more forthcoming." if value < old_val else
                   "Need-to-know basis it is.")
            ),
            "trust": (
                f"Trust parameter at {value} percent. "
                + ("I'll question your orders more." if value < old_val else
                   "Lower than yours, apparently." if value > 80 else
                   "Understood.")
            ),
        }
        return responses.get(param, f"{param.title()} set to {value} percent.")

    registry.register(Command(
        name="settings_adjust",
        patterns=[
            re.compile(
                r'(?:set|adjust|change)\s+'
                r'(?:humor|honesty|discretion|trust)\s+'
                r'(?:to\s+)?\d+'
            ),
        ],
        handler=handle_settings_adjust,
        help_text="Adjust a personality setting (e.g., 'set humor to 50')",
    ))


def register_persistence_commands(registry: CommandRegistry, context: dict) -> None:
    """Register save/load/history commands for conversation persistence."""

    def handle_save(text: str, config: TARSConfig, ctx: dict) -> str | None:
        text_lower = text.lower().strip()
        # Extract optional name after "save" / "save as"
        match = re.match(r'save\s+(?:as\s+)?(.*)', text_lower)
        name = match.group(1).strip() if match else ""
        save_fn = ctx.get("save_conversation")
        if save_fn:
            return save_fn(name if name else None)
        return None

    registry.register(Command(
        name="save",
        patterns=[re.compile(r'^save\b')],
        handler=handle_save,
        help_text="Save conversation (e.g., 'save my-session')",
    ))

    def handle_load(text: str, config: TARSConfig, ctx: dict) -> str | None:
        text_lower = text.lower().strip()
        match = re.match(r'load\s+(.*)', text_lower)
        if not match:
            return "Specify a conversation name to load. Try 'history' to list saved sessions."
        name = match.group(1).strip()
        load_fn = ctx.get("load_conversation")
        if load_fn:
            return load_fn(name)
        return None

    registry.register(Command(
        name="load",
        patterns=[re.compile(r'^load\b')],
        handler=handle_load,
        help_text="Load a saved conversation (e.g., 'load my-session')",
    ))

    def handle_history(text: str, config: TARSConfig, ctx: dict) -> str | None:
        list_fn = ctx.get("list_conversations")
        if list_fn:
            return list_fn()
        return None

    registry.register(Command(
        name="history",
        patterns=[re.compile(r'^history$')],
        handler=handle_history,
        help_text="List saved conversation sessions",
    ))
