"""
TARS Agent — OMLX-backed conversational core.

A facade wiring together the OMLX LLM client, the multi-character
ConversationOrchestrator, and the command registry. OMLX is an
OpenAI-compatible MLX inference server, so all inference stays on your own
hardware — no cloud APIs.

LLM: OMLX server (MiniMax-M2 heretic by default), reached via the OpenAI SDK
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from rich.markup import escape

from config.settings import TARSConfig
from core.prompt import build_tars_system_prompt
from core.commands import CommandRegistry, register_settings_commands, register_persistence_commands
from core.character_commands import register_character_commands
from core.orchestrator import ConversationOrchestrator
from core import persistence


# ── OMLX LLM Wrapper ─────────────────────────────────────────────────────

def _format_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain messages to OpenAI-style chat dicts."""
    formatted = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            formatted.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            formatted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            formatted.append({"role": "assistant", "content": msg.content})
    return formatted


class OMLXLLM:
    """
    OpenAI-compatible client for a local OMLX MLX inference server.

    OMLX (http://127.0.0.1:8000/v1 by default) serves models over the OpenAI
    API with an admin dashboard at /admin/dashboard. We reach it with the
    OpenAI Python SDK, sending the model id exactly as OMLX serves it plus an
    `Authorization: Bearer <api_key>` header. Models load on demand, so the
    first request after a cold start can take a while — hence the generous
    request timeout configured on the client.
    """

    def __init__(self, config: TARSConfig):
        from openai import OpenAI

        self.config = config
        self.client = OpenAI(
            base_url=config.omlx.server_url,
            api_key=config.omlx.api_key,
            timeout=config.omlx.request_timeout,
        )
        self._last_generation_tps: float = 0.0

    def generate(
        self,
        messages: list[BaseMessage],
        on_token: Callable[[str], None] | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a response via the local OMLX server.

        Uses streaming chat completions when on_token is provided,
        non-streaming otherwise. The model id comes straight from config —
        it must match what OMLX serves, or the server returns a 404.

        max_tokens overrides config.omlx.max_tokens for this call only
        (e.g. shorter limits for guest characters).
        """
        import time

        formatted = _format_messages(messages)
        params = dict(
            model=self.config.omlx.model,
            messages=formatted,
            temperature=self.config.omlx.temperature,
            top_p=self.config.omlx.top_p,
            max_tokens=max_tokens or self.config.omlx.max_tokens,
            # Qwen hybrid-thinking (3/3.5/3.6): disable CoT so replies stay
            # short and TTS-clean. Nested under chat_template_kwargs — a
            # top-level enable_thinking is ignored by OMLX/OpenAI-compat.
            # See https://github.com/jundot/omlx/issues/1378
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": self.config.omlx.enable_thinking,
                },
            },
        )

        if on_token is not None:
            stream = self.client.chat.completions.create(**params, stream=True)
            full_text = ""
            n_chunks = 0
            t0 = time.perf_counter()
            for chunk in stream:
                # Some OpenAI-compatible servers emit a trailing usage-only
                # chunk with an empty `choices` list — skip those.
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    full_text += delta
                    n_chunks += 1
                    on_token(delta)
            elapsed = time.perf_counter() - t0
            # Rough client-side tokens/sec (chunk ≈ token for most servers).
            self._last_generation_tps = (n_chunks / elapsed) if elapsed > 0 else 0.0
            return full_text.strip()

        resp = self.client.chat.completions.create(**params)
        content = resp.choices[0].message.content
        return (content or "").strip()

    @property
    def last_generation_tps(self) -> float:
        return self._last_generation_tps


# ── Agent Facade ─────────────────────────────────────────────────────────

class TARSAgent:
    """
    The TARS conversational agent.

    Thin facade that owns the shared config, the OMLX LLM client, the
    multi-character orchestrator, and the extensible command registry
    (settings, save/load/history, character management).
    """

    def __init__(self, config: TARSConfig):
        self.config = config
        self.llm = OMLXLLM(config)
        self.system_prompt = build_tars_system_prompt(config.personality)

        # Multi-character orchestrator (owns the conversation history)
        self.orchestrator = ConversationOrchestrator(config, self.llm, self.system_prompt)

        # Command registry
        self.registry = CommandRegistry()
        ctx = self._command_context()
        register_settings_commands(self.registry, ctx)
        register_persistence_commands(self.registry, ctx)
        register_character_commands(self.registry, ctx)

    def _command_context(self) -> dict:
        """Build the context dict passed to command handlers."""
        return {
            "rebuild_prompt": self._rebuild_prompt,
            "save_conversation": self.save_conversation,
            "load_conversation": self.load_conversation,
            "list_conversations": self.list_conversations,
            "orchestrator": self.orchestrator,
        }

    def _rebuild_prompt(self) -> None:
        """Rebuild system prompt from current personality and update state."""
        self.system_prompt = build_tars_system_prompt(self.config.personality)
        self.orchestrator.tars_system_prompt = self.system_prompt

    # ── Persistence Methods ──────────────────────────────────────────────

    def save_conversation(self, name: str | None = None) -> str:
        """Save current conversation to disk."""
        if not name:
            name = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")

        personality_dict = {
            "humor": self.config.personality.humor,
            "honesty": self.config.personality.honesty,
            "discretion": self.config.personality.discretion,
            "trust": self.config.personality.trust,
        }

        try:
            filepath = persistence.save_conversation(
                name=name,
                messages=self.orchestrator.messages,
                personality=personality_dict,
                context_summary=self.orchestrator.context_summary,
                active_characters=self.orchestrator._active_ids,
            )
        except ValueError as e:
            return str(e)
        return f"Conversation saved as '{name}'. File: {filepath.name}"

    def load_conversation(self, name: str) -> str:
        """Load a saved conversation from disk."""
        data = persistence.load_conversation(name)
        if not data:
            return f"No saved conversation named '{escape(name)}'. Try 'history' to list sessions."

        # Restore messages to orchestrator
        self.orchestrator.messages = data["messages"]
        self.orchestrator.context_summary = data.get("context_summary", "")

        # Restore active characters
        active = data.get("active_characters", ["tars"])
        self.orchestrator._active_ids = active

        # Restore personality
        p = data.get("personality", {})
        for attr in ("humor", "honesty", "discretion", "trust"):
            if attr in p:
                setattr(self.config.personality, attr, p[attr])
        self._rebuild_prompt()

        msg_count = data.get("message_count", len(data["messages"]))
        return f"Conversation '{name}' restored. {msg_count} messages loaded. Personality recalibrated."

    def list_conversations(self) -> str:
        """List all saved conversation sessions."""
        sessions = persistence.list_conversations()
        if not sessions:
            return "No saved conversations found. Use 'save' to store a session."

        lines = ["Saved sessions:"]
        for s in sessions:
            lines.append(f"  - {s['name']} ({s['message_count']} messages, {s['saved_at']})")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset conversation history, keep personality."""
        self.orchestrator.reset()
