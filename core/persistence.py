"""
TARS Conversation Persistence — JSON-based save/load.

Saves conversation history and personality state to the conversations/ directory.
Each session is a JSON file with messages, personality, and metadata.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from rich.markup import escape


CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"

# Session names become filenames — allow only filename-safe characters
# (letters, digits, spaces, dashes, underscores). Anything else (path
# separators, dots) is rejected to prevent path traversal.
_SAFE_NAME = re.compile(r"^[\w\- ]+$", re.UNICODE)


def is_valid_name(name: str) -> bool:
    """Check whether a session name is safe to use as a filename."""
    return bool(name) and bool(_SAFE_NAME.match(name))


def _sanitize_name(name: str) -> str:
    """Validate a session name for use as a filename. Raises ValueError."""
    name = name.strip()
    if not is_valid_name(name):
        raise ValueError(
            f"Invalid session name {escape(name)!r}. "
            "Use letters, numbers, spaces, dashes or underscores only."
        )
    return name


def _message_to_dict(msg: BaseMessage) -> dict:
    """Serialize a LangChain message to a plain dict."""
    if isinstance(msg, SystemMessage):
        role = "system"
    elif isinstance(msg, HumanMessage):
        role = "human"
    elif isinstance(msg, AIMessage):
        role = "ai"
    else:
        role = "unknown"
    d = {"role": role, "content": msg.content}
    # Preserve the name field for multi-character conversations
    name = getattr(msg, "name", None)
    if name:
        d["name"] = name
    return d


def _dict_to_message(d: dict) -> BaseMessage:
    """Deserialize a plain dict back to a LangChain message."""
    role = d["role"]
    content = d["content"]
    name = d.get("name")
    if role == "system":
        return SystemMessage(content=content)
    elif role == "human":
        return HumanMessage(content=content, name=name) if name else HumanMessage(content=content)
    elif role == "ai":
        return AIMessage(content=content, name=name) if name else AIMessage(content=content)
    return HumanMessage(content=content)


def save_conversation(
    name: str,
    messages: list[BaseMessage],
    personality: dict,
    context_summary: str = "",
    active_characters: list[str] | None = None,
) -> Path:
    """
    Save conversation to a JSON file.

    Args:
        name: Session name (used as filename stem).
        messages: Full message history.
        personality: Dict with humor/honesty/discretion/trust values.
        context_summary: Rolling context summary string.
        active_characters: List of active character IDs.

    Returns:
        Path to the saved file.

    Raises:
        ValueError: If the session name isn't filename-safe.
    """
    name = _sanitize_name(name)
    CONVERSATIONS_DIR.mkdir(exist_ok=True)

    data = {
        "name": name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "message_count": len(messages),
        "context_summary": context_summary,
        "personality": personality,
        "messages": [_message_to_dict(m) for m in messages],
        "active_characters": active_characters or ["tars"],
    }

    filepath = CONVERSATIONS_DIR / f"{name}.json"
    filepath.write_text(json.dumps(data, indent=2))
    return filepath


def load_conversation(name: str) -> Optional[dict]:
    """
    Load a saved conversation.

    Returns:
        Dict with keys: messages, personality, context_summary, name, saved_at.
        None if the file doesn't exist or the name isn't filename-safe.
    """
    name = name.strip()
    if not is_valid_name(name):
        return None
    filepath = CONVERSATIONS_DIR / f"{name}.json"
    if not filepath.exists():
        return None

    data = json.loads(filepath.read_text())
    data["messages"] = [_dict_to_message(m) for m in data["messages"]]
    return data


def list_conversations() -> list[dict]:
    """
    List all saved conversations.

    Returns:
        List of dicts with: name, saved_at, message_count.
    """
    if not CONVERSATIONS_DIR.exists():
        return []

    sessions = []
    for filepath in sorted(CONVERSATIONS_DIR.glob("*.json")):
        try:
            data = json.loads(filepath.read_text())
            sessions.append({
                "name": data.get("name", filepath.stem),
                "saved_at": data.get("saved_at", "unknown"),
                "message_count": data.get("message_count", 0),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return sessions
