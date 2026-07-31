"""
Character Commands — call, dismiss, and roster management.

Registers with the existing CommandRegistry to handle natural language
commands for summoning and dismissing Interstellar crew members.

Handles natural speech patterns like:
- "call brand"
- "tars, call brand"
- "hey tars call brand and mann"
- "call brand, also call dr mann, also call prof. brand and also call murphy"
"""

from __future__ import annotations

import re

from rich.markup import escape

from config.settings import TARSConfig
from core.commands import CommandRegistry, Command
from core.characters import resolve_character, CHARACTER_REGISTRY


# Optional "tars" / "hey tars," prefix before the actual command verb
_TARS_PREFIX = r'(?:(?:hey\s+)?tars[,:\s]\s*)?'

# Call verbs and dismiss verbs. Deliberately excludes generic verbs like
# "get" — "get me a status report" is not a summon request.
_CALL_VERBS = r'(?:call|summon|bring in|wake up|invite)'
_DISMISS_VERBS = r'(?:dismiss|send away|remove|goodbye)'

# Everybody synonyms
_EVERYONE = r'(?:everyone|all|the crew|the whole crew|everybody)'

# Patterns that match call/dismiss with optional TARS prefix
_CALL_PATTERN = re.compile(rf'^{_TARS_PREFIX}{_CALL_VERBS}\s+.+')
_CALL_EVERYONE_PATTERN = re.compile(rf'^{_TARS_PREFIX}{_CALL_VERBS}\s+{_EVERYONE}')
_DISMISS_PATTERN = re.compile(rf'^{_TARS_PREFIX}{_DISMISS_VERBS}\s+.+')
_DISMISS_EVERYONE_PATTERN = re.compile(rf'^{_TARS_PREFIX}{_DISMISS_VERBS}\s+{_EVERYONE}')


def _extract_names(text: str, verbs_pattern: str) -> list[str]:
    """
    Extract character names from a command that may list multiple characters.

    Handles patterns like:
    - "call brand"
    - "tars call brand and mann"
    - "call brand, also call dr mann, also call prof. brand and also call murphy"
    - "call brand, mann, murphy"
    """
    # Strip TARS prefix
    cleaned = re.sub(rf'^(?:(?:hey\s+)?tars[,:\s]\s*)', '', text, count=1)
    # Remove all occurrences of the verb (handles "also call X, also call Y")
    cleaned = re.sub(rf'(?:also\s+)?{verbs_pattern}\s*', ' ', cleaned)
    # Split on delimiters: commas, "and", "also"
    parts = re.split(r'\s*[,]\s*|\s+and\s+|\s+also\s+', cleaned)
    # Clean up each part
    names = [p.strip().strip(',').strip() for p in parts if p.strip()]
    return names


def register_character_commands(registry: CommandRegistry, context: dict) -> None:
    """Register all character management commands."""

    def _get_orchestrator(ctx: dict):
        return ctx.get("orchestrator")

    # ── Call / Summon ─────────────────────────────────────────────────

    def handle_call(text: str, config: TARSConfig, ctx: dict) -> str | None:
        orchestrator = _get_orchestrator(ctx)
        if not orchestrator:
            return None

        text_lower = text.lower().strip()

        # "call everyone / all / the crew"
        if _CALL_EVERYONE_PATTERN.match(text_lower):
            return orchestrator.call_everyone()

        # Extract all character names from the command
        names = _extract_names(text_lower, _CALL_VERBS)
        if not names:
            return None

        results = []
        for name in names:
            char = resolve_character(name)
            if char:
                results.append(orchestrator.call_character(char.id))
            else:
                available = ", ".join(
                    c.display_name for c in CHARACTER_REGISTRY.values()
                    if not c.is_primary
                )
                results.append(
                    f"I don't recognize '{escape(name)}'. Available: {available}."
                )

        return " ".join(results)

    registry.register(Command(
        name="call_character",
        patterns=[_CALL_PATTERN],
        handler=handle_call,
        help_text="Summon a crew member (e.g., 'call brand', 'call everyone')",
    ))

    # ── Dismiss ──────────────────────────────────────────────────────

    def handle_dismiss(text: str, config: TARSConfig, ctx: dict) -> str | None:
        orchestrator = _get_orchestrator(ctx)
        if not orchestrator:
            return None

        text_lower = text.lower().strip()

        # "dismiss everyone / all"
        if _DISMISS_EVERYONE_PATTERN.match(text_lower):
            return orchestrator.dismiss_everyone()

        # Extract all character names
        names = _extract_names(text_lower, _DISMISS_VERBS)
        if not names:
            return None

        results = []
        for name in names:
            char = resolve_character(name)
            if char:
                results.append(orchestrator.dismiss_character(char.id))
            else:
                results.append(f"I don't recognize '{escape(name)}'.")

        return " ".join(results)

    registry.register(Command(
        name="dismiss_character",
        patterns=[_DISMISS_PATTERN],
        handler=handle_dismiss,
        help_text="Dismiss a crew member (e.g., 'dismiss mann', 'dismiss everyone')",
    ))

    # ── Who's Here ───────────────────────────────────────────────────

    def handle_who(text: str, config: TARSConfig, ctx: dict) -> str | None:
        orchestrator = _get_orchestrator(ctx)
        if not orchestrator:
            return None
        return orchestrator.who_is_here()

    registry.register(Command(
        name="who_is_here",
        patterns=[
            "who's here",
            "who is here",
            "roll call",
            "crew status",
            re.compile(r"^(?:(?:hey\s+)?tars[,:\s]\s*)?who'?s here\??$"),
        ],
        handler=handle_who,
        help_text="List active crew members",
    ))
