"""
Multi-Character Conversation Orchestrator

Manages multi-party Interstellar crew conversations. Characters take turns
responding, with buffered silence detection so characters can opt out of
irrelevant exchanges. All characters share a single LLM — each is just
a different system prompt + voice preset.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from config.settings import TARSConfig
from core.characters import (
    Character,
    CHARACTER_REGISTRY,
    TARS_MULTI_PARTY_ADDENDUM,
    resolve_character,
)


SILENCE_MARKERS = {"[silent]", "[silence]", "[ silent ]", "[silent]."}
SILENCE_BUFFER_SIZE = 20


@dataclass
class CharacterResponse:
    """Result of a single character's turn."""
    character: Character
    text: str
    silent: bool


class ConversationOrchestrator:
    """
    Orchestrates multi-party conversations between Interstellar crew members.

    TARS is always present. Other characters are summoned/dismissed on demand.
    Each character generates a response in turn order, seeing all prior responses
    from the same round. Characters can stay [SILENT] when they have nothing to add.
    """

    def __init__(self, config: TARSConfig, llm, tars_system_prompt: str):
        self.config = config
        self.llm = llm
        self.tars_system_prompt = tars_system_prompt
        self.messages: list[BaseMessage] = []
        self.context_summary: str = ""

        # TARS is always active and always first
        self._active_ids: list[str] = ["tars"]

    @property
    def active_characters(self) -> list[Character]:
        """Active characters in turn order (TARS first)."""
        return [CHARACTER_REGISTRY[cid] for cid in self._active_ids if cid in CHARACTER_REGISTRY]

    @property
    def has_guests(self) -> bool:
        return len(self._active_ids) > 1

    # ── Character Management ─────────────────────────────────────────────

    def call_character(self, character_id: str) -> str:
        """Summon a character to the conversation."""
        char = CHARACTER_REGISTRY.get(character_id)
        if not char:
            available = ", ".join(
                c.display_name for c in CHARACTER_REGISTRY.values() if not c.is_primary
            )
            return f"I don't recognize that crew member. Available: {available}."

        if char.is_primary:
            return "You can't call me, Cooper. I'm already here. Bolted to the ship."

        if character_id in self._active_ids:
            return f"{char.display_name} is already here, Cooper."

        self._active_ids.append(character_id)
        return f"{char.display_name} has joined the conversation."

    def dismiss_character(self, character_id: str) -> str:
        """Remove a character from the conversation."""
        char = CHARACTER_REGISTRY.get(character_id)
        if not char:
            return "I don't recognize that crew member."

        if char.is_primary:
            return "You can't dismiss me, Cooper. I'm bolted to the ship."

        if character_id not in self._active_ids:
            return f"{char.display_name} isn't here, Cooper."

        self._active_ids.remove(character_id)
        return f"{char.display_name} has left the conversation."

    def call_everyone(self) -> str:
        """Summon all available characters."""
        added = []
        for cid, char in CHARACTER_REGISTRY.items():
            if not char.is_primary and cid not in self._active_ids:
                self._active_ids.append(cid)
                added.append(char.display_name)
        if not added:
            return "Everyone's already here, Cooper."
        return f"{', '.join(added)} — all present. It's getting crowded in here."

    def dismiss_everyone(self) -> str:
        """Dismiss all guest characters, keeping TARS."""
        dismissed = [
            CHARACTER_REGISTRY[cid].display_name
            for cid in self._active_ids if cid != "tars"
        ]
        self._active_ids = ["tars"]
        if not dismissed:
            return "It's just us, Cooper. As usual."
        return f"{', '.join(dismissed)} dismissed. Just you and me now."

    def who_is_here(self) -> str:
        """List active characters."""
        names = [c.display_name for c in self.active_characters]
        if len(names) == 1:
            return f"Just me, Cooper. {names[0]}. Want to call someone? Try 'call brand'."
        return "Present: " + ", ".join(names) + "."

    # ── Core Generation ──────────────────────────────────────────────────

    def generate_round(
        self,
        user_input: str,
        on_character_start: Callable[[Character], None] | None = None,
        on_character_token: Callable[[str, str], None] | None = None,
        on_character_end: Callable[[Character, str], None] | None = None,
    ) -> list[CharacterResponse]:
        """
        Generate responses from all active characters for a single user turn.

        After the main round, if any character directly addressed another
        character with a question, the addressed character gets a follow-up
        turn (one follow-up pass max, to prevent infinite loops).

        Args:
            user_input: Cooper's message.
            on_character_start: Called when a character starts a non-silent response.
                                Receives the Character.
            on_character_token: Called per streaming token. Receives (character_id, token).
            on_character_end: Called after a character finishes. Receives (Character, full_text).

        Returns:
            List of CharacterResponse for this round.
        """
        callbacks = (on_character_start, on_character_token, on_character_end)

        # Add Cooper's message to shared history
        self.messages.append(HumanMessage(content=user_input, name="Cooper"))

        # ── Main round ───────────────────────────────────────────────
        # Responses stay in round_responses only; committed to self.messages after.
        round_responses: list[CharacterResponse] = []

        for character in self.active_characters:
            resp = self._generate_character_response(
                character, round_responses, *callbacks
            )
            round_responses.append(resp)

        # Commit main-round responses to persistent history
        self._commit_responses(round_responses)

        # ── Follow-up round ──────────────────────────────────────────
        # If a character was addressed by name + "?" in someone else's
        # response, give them one extra turn so they can actually answer.
        followup_ids = self._find_addressed_characters(round_responses)
        if followup_ids:
            followup_responses: list[CharacterResponse] = []
            for cid in followup_ids:
                character = CHARACTER_REGISTRY[cid]
                # self.messages now has the main round; followup_responses
                # tracks only the follow-up pass (no duplication).
                resp = self._generate_character_response(
                    character, followup_responses, *callbacks
                )
                followup_responses.append(resp)

            self._commit_responses(followup_responses)
            round_responses.extend(followup_responses)

        # Trim history if needed
        self._trim_history()

        return round_responses

    # ── Single-character generation ──────────────────────────────────

    def _generate_character_response(
        self,
        character: Character,
        pending_responses: list[CharacterResponse],
        on_character_start: Callable[[Character], None] | None = None,
        on_character_token: Callable[[str, str], None] | None = None,
        on_character_end: Callable[[Character, str], None] | None = None,
    ) -> CharacterResponse:
        """
        Generate a single character's response with buffered silence detection.

        Args:
            character: The character to generate for.
            pending_responses: Responses from this pass that are NOT yet in
                               self.messages (avoids duplication).
        """
        char_messages = self._build_messages_for_character(character, pending_responses)

        # Determine max tokens
        max_tokens = character.max_tokens
        if not character.is_primary:
            max_tokens = min(max_tokens, self.config.multi_character_max_tokens)

        # Stream generate with buffered silence detection
        buffer = ""
        started = False
        full_text = ""

        # Save and temporarily override max_tokens
        original_max_tokens = self.config.omlx.max_tokens
        self.config.omlx.max_tokens = max_tokens

        # Capture character in a local variable for the closure
        _char = character

        try:
            def _on_token(token: str):
                nonlocal buffer, started, full_text
                full_text += token

                if not started:
                    buffer += token
                    if len(buffer) >= SILENCE_BUFFER_SIZE:
                        if not self._is_silent(buffer):
                            started = True
                            if on_character_start:
                                on_character_start(_char)
                            if on_character_token:
                                on_character_token(_char.id, buffer)
                else:
                    if on_character_token:
                        on_character_token(_char.id, token)

            self.llm.generate(char_messages, on_token=_on_token)
        finally:
            self.config.omlx.max_tokens = original_max_tokens

        full_text = full_text.strip()
        silent = self._is_silent(full_text)

        # If we buffered but never started and it's not silent, flush now
        if not started and not silent and buffer:
            if on_character_start:
                on_character_start(_char)
            if on_character_token:
                on_character_token(_char.id, buffer)

        if not silent and on_character_end:
            on_character_end(_char, full_text)

        return CharacterResponse(character=character, text=full_text, silent=silent)

    def _commit_responses(self, responses: list[CharacterResponse]) -> None:
        """Add non-silent responses to persistent message history."""
        for resp in responses:
            if not resp.silent:
                self.messages.append(
                    AIMessage(content=resp.text, name=resp.character.id)
                )

    # ── Follow-up detection ──────────────────────────────────────────

    def _find_addressed_characters(
        self, round_responses: list[CharacterResponse]
    ) -> list[str]:
        """
        Find characters that were directly addressed with a question.

        Returns character IDs (in turn order) that should get a follow-up
        turn. A character is "addressed" if another character's response
        mentions them by display name AND contains a question mark.
        """
        addressed: set[str] = set()
        # Characters who already spoke this round
        spoke_ids = {r.character.id for r in round_responses if not r.silent}

        for resp in round_responses:
            if resp.silent:
                continue
            # Only look at responses that contain questions
            if "?" not in resp.text:
                continue
            text_lower = resp.text.lower()
            for char in self.active_characters:
                if char.id == resp.character.id:
                    continue  # Can't address yourself
                if char.display_name.lower() in text_lower:
                    addressed.add(char.id)

        # Return in turn order, only characters that already spoke
        # (they need a follow-up because they went before the asker)
        return [cid for cid in self._active_ids if cid in addressed and cid in spoke_ids]

    # ── Message building ─────────────────────────────────────────────

    def _build_messages_for_character(
        self,
        character: Character,
        pending_responses: list[CharacterResponse],
    ) -> list[BaseMessage]:
        """
        Build the message list from a character's perspective.

        Uses two sources, with no overlap:
        - self.messages: persistent history (prior rounds, already committed)
        - pending_responses: current-pass responses NOT yet in self.messages

        Role mapping (critical — LLM only understands system/user/assistant):
        - Character's own prior responses → assistant
        - Cooper's messages → user with "Cooper: " prefix
        - Other characters' responses → user with "{name}: " prefix
        """
        result: list[BaseMessage] = []

        # System prompt
        if character.is_primary:
            prompt = self.tars_system_prompt
            if self.has_guests:
                prompt += TARS_MULTI_PARTY_ADDENDUM
        else:
            prompt = character.system_prompt

        # Add who's present context
        if self.has_guests:
            names = [c.display_name for c in self.active_characters]
            prompt += f"\n\n[Present in this conversation: Cooper (human), {', '.join(names)}]"

        result.append(SystemMessage(content=prompt))

        # Context summary if available
        if self.context_summary:
            result.append(
                SystemMessage(content=f"[Previous conversation summary: {self.context_summary}]")
            )

        # Persistent history (prior rounds, already committed)
        for msg in self.messages:
            result.append(self._map_message_role(msg, character))

        # Current-pass responses not yet in self.messages
        for resp in pending_responses:
            if resp.silent:
                continue
            if resp.character.id == character.id:
                result.append(AIMessage(content=resp.text))
            else:
                result.append(
                    HumanMessage(content=f"{resp.character.display_name}: {resp.text}")
                )

        return result

    def _map_message_role(self, msg: BaseMessage, character: Character) -> BaseMessage:
        """Map a history message to the correct role for a given character."""
        name = getattr(msg, "name", None) or ""

        if isinstance(msg, HumanMessage):
            content = f"Cooper: {msg.content}" if self.has_guests else msg.content
            return HumanMessage(content=content)
        elif isinstance(msg, AIMessage):
            if name == character.id:
                return AIMessage(content=msg.content)
            else:
                speaker = CHARACTER_REGISTRY.get(name)
                display = speaker.display_name if speaker else name
                return HumanMessage(content=f"{display}: {msg.content}")
        return msg

    def _is_silent(self, text: str) -> bool:
        """Check if response is a silence marker."""
        cleaned = text.strip().lower()
        # Check exact markers
        if cleaned in SILENCE_MARKERS:
            return True
        # Check if the response is essentially just the silence tag with minor extras
        if re.match(r'^\[?\s*silent\s*\]?\.?\s*$', cleaned):
            return True
        return False

    def _trim_history(self) -> None:
        """Trim message history with summarization when it gets too long."""
        max_messages = self.config.conversation_memory_k
        if len(self.messages) <= max_messages:
            return

        # Messages being dropped
        dropped = self.messages[:-(max_messages)]
        self.messages = self.messages[-(max_messages):]

        # Summarize dropped messages
        self.context_summary = self._summarize_context(dropped, self.context_summary)

    def _summarize_context(self, dropped: list[BaseMessage], existing_summary: str) -> str:
        """Summarize dropped messages into a rolling context summary."""
        lines = []
        for msg in dropped:
            name = getattr(msg, "name", None)
            if isinstance(msg, HumanMessage):
                speaker = name or "Cooper"
                lines.append(f"{speaker}: {msg.content}")
            elif isinstance(msg, AIMessage):
                speaker = name or "TARS"
                if speaker in CHARACTER_REGISTRY:
                    speaker = CHARACTER_REGISTRY[speaker].display_name
                lines.append(f"{speaker}: {msg.content}")
        dropped_text = "\n".join(lines)

        if existing_summary:
            prompt_text = (
                f"Previous conversation summary:\n{existing_summary}\n\n"
                f"Additional conversation that needs to be incorporated:\n{dropped_text}\n\n"
                f"Provide an updated summary in 2-3 sentences covering the key topics and context."
            )
        else:
            prompt_text = (
                f"Conversation to summarize:\n{dropped_text}\n\n"
                f"Summarize this conversation in 2-3 sentences covering the key topics and context."
            )

        summary_messages = [
            SystemMessage(content="You are a concise summarizer. Respond only with the summary."),
            HumanMessage(content=prompt_text),
        ]

        return self.llm.generate(summary_messages)

    def reset(self) -> None:
        """Clear conversation history and dismiss all guests."""
        self.messages = []
        self.context_summary = ""
        self._active_ids = ["tars"]
