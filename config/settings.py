"""
TARS-AI Configuration — fully OMLX-backed (LLM + TTS)

Both models run on a local OMLX server: an OpenAI-compatible MLX inference
server (default http://127.0.0.1:8000/v1) with an admin dashboard at
/admin/dashboard. The LLM uses /v1/chat/completions; TTS (Qwen3-TTS Voice
Design) uses /v1/audio/speech. No cloud APIs, and nothing runs locally on the
client except audio playback.

LLM: OMLX (MiniMax-M2 heretic by default)  |  TTS: OMLX (Qwen3-TTS Voice Design)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts.yaml"

def _load_prompts() -> dict:
    with open(PROMPTS_PATH) as f:
        return yaml.safe_load(f)


# ── TARS Personality Knobs ───────────────────────────────────────────────

@dataclass
class TARSPersonality:
    """
    Adjustable personality parameters, just like in the movie.
    Cooper: "Hey TARS, what's your honesty parameter?"
    TARS: "90 percent."
    Cooper: "90? ... Adjust it to 95."
    """
    humor: int = 75          # 0-100: dry wit / sarcasm level
    honesty: int = 90        # 0-100: bluntness vs diplomacy
    discretion: int = 85     # 0-100: information sharing restraint
    trust: int = 70          # 0-100: willingness to follow unusual orders

    def __post_init__(self):
        for attr in ("humor", "honesty", "discretion", "trust"):
            val = getattr(self, attr)
            if not 0 <= val <= 100:
                raise ValueError(f"{attr} must be 0-100, got {val}")

    def summary(self) -> str:
        return (
            f"Humor: {self.humor}% | Honesty: {self.honesty}% | "
            f"Discretion: {self.discretion}% | Trust: {self.trust}%"
        )

    def to_prompt_block(self) -> str:
        """Convert personality settings into system prompt directives."""
        scales = _load_prompts()["personality_scales"]
        blocks = []
        for attr in ("humor", "honesty", "discretion"):
            value = getattr(self, attr)
            for tier in scales[attr]:
                if value >= tier["min"]:
                    blocks.append(tier["directive"])
                    break
        return "\n".join(blocks)


# ── OMLX LLM Configuration ───────────────────────────────────────────────

@dataclass
class OMLXConfig:
    """
    Connection + sampling settings for a local OMLX server.

    OMLX is an OpenAI-compatible MLX inference server. TARS reaches it with
    the OpenAI SDK, so `model` must match *exactly* what OMLX serves — check
    `GET {server_url}/models` or the admin dashboard. OMLX loads models on
    demand, so the first request after a cold start can be slow; `request_timeout`
    is deliberately generous to cover that initial load.
    """

    # Model id — must match a model OMLX is actually serving (not a HuggingFace path).
    model: str = "MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX"

    # OMLX OpenAI-compatible endpoint. Admin dashboard lives at .../admin/dashboard.
    server_url: str = "http://127.0.0.1:8000/v1"

    # OMLX local dev key — sent as `Authorization: Bearer <api_key>`.
    api_key: str = "test"

    # Sampling
    max_tokens: int = 768
    temperature: float = 0.7
    top_p: float = 0.9

    # OMLX loads models on demand — first request can take minutes. Seconds.
    request_timeout: float = 1800.0

    @property
    def dashboard_url(self) -> str:
        """Best-effort admin dashboard URL derived from the /v1 endpoint."""
        base = self.server_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        return f"{base.rstrip('/')}/admin/dashboard"


# ── TTS Configuration (served by OMLX) ───────────────────────────────────

@dataclass
class TTSConfig:
    """
    Text-to-speech via the OMLX server's OpenAI-compatible /v1/audio/speech.

    OMLX serves the TTS model (Qwen3-TTS Voice Design) alongside the LLM, so
    `model` must match what OMLX serves (GET /v1/models). The `voice_desc` is
    sent as the OpenAI `voice` field; oMLX maps it to the model's `instruct`
    for VoiceDesign models. OMLX returns audio in `response_format` (WAV).
    """

    model: str = "Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16"
    voice_desc: str = "A deep, measured, authoritative American male voice. Military precision. Deliberate pauses."
    speed: float = 1.0
    response_format: str = "wav"


# ── Master Config ────────────────────────────────────────────────────────

@dataclass
class TARSConfig:
    personality: TARSPersonality = field(default_factory=TARSPersonality)
    omlx: OMLXConfig = field(default_factory=OMLXConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    audio_output_dir: str = "audio_output"
    play_audio: bool = True           # Auto-play generated audio
    save_audio: bool = True           # Keep audio files
    conversation_memory_k: int = 20   # Messages to keep in context
    multi_character_max_tokens: int = 256  # Shorter responses for guest characters

    def validate(self):
        """Sanity-check config before launch.

        Both the LLM and TTS run on the remote OMLX server, and audio playback
        is cross-platform (sounddevice, with afplay / mpv / ffplay fallbacks),
        so there's no Apple-Silicon requirement on the client. Personality
        ranges are validated in TARSPersonality.__post_init__.
        """
        return None
