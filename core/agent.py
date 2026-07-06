"""
TARS LangGraph Agent — OMLX-backed

A stateful conversational agent using LangGraph with a local OMLX server as
the LLM backend. OMLX is an OpenAI-compatible MLX inference server, so all
inference stays on your own hardware — no cloud APIs.

Graph: [input] -> generate_response -> [output]
LLM:   OMLX server (MiniMax-M2 heretic by default), reached via the OpenAI SDK
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, TypedDict, Sequence, Optional, Callable

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from config.settings import TARSConfig
from core.prompt import build_tars_system_prompt
from core.commands import CommandRegistry, register_settings_commands, register_persistence_commands
from core.character_commands import register_character_commands
from core.orchestrator import ConversationOrchestrator
from core import persistence


# ── State Definition ─────────────────────────────────────────────────────

class TARSState(TypedDict):
    """Graph state: conversation messages with auto-accumulation."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    personality_summary: str
    context_summary: str  # rolling summary of trimmed messages


# ── MLX LLM Wrapper ─────────────────────────────────────────────────────

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
    ) -> str:
        """
        Generate a response via the local OMLX server.

        Uses streaming chat completions when on_token is provided,
        non-streaming otherwise. The model id comes straight from config —
        it must match what OMLX serves, or the server returns a 404.
        """
        import time

        formatted = _format_messages(messages)
        params = dict(
            model=self.config.omlx.model,
            messages=formatted,
            temperature=self.config.omlx.temperature,
            top_p=self.config.omlx.top_p,
            max_tokens=self.config.omlx.max_tokens,
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
        return resp.choices[0].message.content.strip()

    @property
    def last_generation_tps(self) -> float:
        return self._last_generation_tps


# ── Graph Nodes ──────────────────────────────────────────────────────────

class TARSAgent:
    """
    The TARS conversational agent built on LangGraph + a local OMLX server.

    Graph structure:
        [input] -> generate_response -> [output]

    Features:
    - Extensible command registry (settings, save/load/history)
    - Conversation persistence (JSON-based)
    - Smart context management (summarize-then-trim)
    - Streaming token output
    """

    def __init__(self, config: TARSConfig):
        self.config = config
        self.llm = OMLXLLM(config)
        self.system_prompt = build_tars_system_prompt(config.personality)
        self.graph = self._build_graph()
        self.app = self.graph.compile()
        self._on_token: Callable[[str], None] | None = None

        # Conversation state persisted across invocations
        self._state: TARSState = {
            "messages": [SystemMessage(content=self.system_prompt)],
            "personality_summary": config.personality.summary(),
            "context_summary": "",
        }

        # Multi-character orchestrator
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
            "save_conversation": self._save_conversation,
            "load_conversation": self._load_conversation,
            "list_conversations": self._list_conversations,
            "state": self._state,
            "orchestrator": self.orchestrator,
        }

    def _rebuild_prompt(self) -> None:
        """Rebuild system prompt from current personality and update state."""
        self.system_prompt = build_tars_system_prompt(self.config.personality)
        self._state["messages"][0] = SystemMessage(content=self.system_prompt)
        self._state["personality_summary"] = self.config.personality.summary()
        self.orchestrator.tars_system_prompt = self.system_prompt

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph processing pipeline."""
        graph = StateGraph(TARSState)

        # Nodes
        graph.add_node("generate", self._generate_node)

        # Edges (simple linear for now — extend for tools/branching)
        graph.set_entry_point("generate")
        graph.add_edge("generate", END)

        return graph

    def _summarize_context(self, dropped: list[BaseMessage], existing_summary: str) -> str:
        """Summarize dropped messages into a rolling context summary."""
        # Format dropped messages
        lines = []
        for msg in dropped:
            if isinstance(msg, HumanMessage):
                lines.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"TARS: {msg.content}")
        dropped_text = "\n".join(lines)

        # Build summarization prompt
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

    def _generate_node(self, state: TARSState) -> dict:
        """Core generation node: invoke MLX LLM with full conversation context."""
        messages = list(state["messages"])
        context_summary = state.get("context_summary", "")

        # Smart context trimming with summarization
        max_messages = self.config.conversation_memory_k
        if len(messages) > max_messages + 1:  # +1 for system prompt
            system = messages[0]
            # Messages being dropped (between system prompt and keep-window)
            dropped = messages[1:-(max_messages)]
            recent = messages[-(max_messages):]

            # Summarize dropped messages
            context_summary = self._summarize_context(dropped, context_summary)

            # Build message list with summary injected
            summary_msg = SystemMessage(
                content=f"[Previous conversation summary: {context_summary}]"
            )
            messages = [system, summary_msg] + recent

        response_text = self.llm.generate(messages, on_token=self._on_token)
        return {
            "messages": [AIMessage(content=response_text)],
            "context_summary": context_summary,
        }

    def chat(
        self,
        user_input: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """
        Send a message to TARS and get a response.

        Args:
            user_input: The human's message text.
            on_token: Optional callback invoked with each token chunk as it streams.

        Returns:
            TARS's response text.
        """
        # Check for registered commands (settings, persistence, etc.)
        cmd_response = self.registry.dispatch(
            user_input, self.config, self._command_context()
        )
        if cmd_response:
            return cmd_response

        # Add human message to state
        self._state["messages"] = list(self._state["messages"]) + [
            HumanMessage(content=user_input)
        ]

        # Set streaming callback for the generate node
        self._on_token = on_token

        # Run graph
        result = self.app.invoke(self._state)

        # Clear streaming callback
        self._on_token = None

        # Update state with new messages and context summary
        self._state["messages"] = result["messages"]
        self._state["context_summary"] = result.get("context_summary", "")

        # Extract response text
        last_message = result["messages"][-1]
        return last_message.content

    # ── Persistence Methods ──────────────────────────────────────────────

    def _save_conversation(self, name: str | None = None) -> str:
        """Save current conversation to disk."""
        if not name:
            name = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")

        personality_dict = {
            "humor": self.config.personality.humor,
            "honesty": self.config.personality.honesty,
            "discretion": self.config.personality.discretion,
            "trust": self.config.personality.trust,
        }

        filepath = persistence.save_conversation(
            name=name,
            messages=self.orchestrator.messages,
            personality=personality_dict,
            context_summary=self.orchestrator.context_summary,
            active_characters=self.orchestrator._active_ids,
        )
        return f"Conversation saved as '{name}'. File: {filepath.name}"

    def _load_conversation(self, name: str) -> str:
        """Load a saved conversation from disk."""
        data = persistence.load_conversation(name)
        if not data:
            return f"No saved conversation named '{name}'. Try 'history' to list sessions."

        # Restore messages to orchestrator
        self.orchestrator.messages = data["messages"]
        self.orchestrator.context_summary = data.get("context_summary", "")

        # Restore active characters
        active = data.get("active_characters", ["tars"])
        self.orchestrator._active_ids = active

        # Also sync legacy state
        self._state["messages"] = [SystemMessage(content=self.system_prompt)] + data["messages"]
        self._state["context_summary"] = data.get("context_summary", "")

        # Restore personality
        p = data.get("personality", {})
        for attr in ("humor", "honesty", "discretion", "trust"):
            if attr in p:
                setattr(self.config.personality, attr, p[attr])
        self._rebuild_prompt()

        msg_count = data.get("message_count", len(data["messages"]))
        return f"Conversation '{name}' restored. {msg_count} messages loaded. Personality recalibrated."

    def _list_conversations(self) -> str:
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
        self._state = {
            "messages": [SystemMessage(content=self.system_prompt)],
            "personality_summary": self.config.personality.summary(),
            "context_summary": "",
        }
        self.orchestrator.reset()
