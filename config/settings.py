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
from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts.yaml"

@lru_cache(maxsize=1)
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

    # Qwen3/3.5/3.6 hybrid-thinking models default to "think out loud" on OMLX.
    # That dumps multi-paragraph reasoning into the reply (and TTS). Off by
    # default for a conversational agent; pass True to re-enable chain-of-thought.
    # Sent as extra_body chat_template_kwargs.enable_thinking (OMLX/OpenAI-compat).
    enable_thinking: bool = False

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
    # Fallback voice description, used only when the caller doesn't pass one
    # explicitly. The canonical TARS default lives in core/characters.py
    # (TARS_VOICE_DESC); the CLI --voice-desc flag overrides it at startup.
    voice_desc: str | None = None
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
        """Sanity-check config before launch. Raises ValueError on bad values.

        Both the LLM and TTS run on the remote OMLX server, and audio playback
        is cross-platform (sounddevice, with afplay / mpv / ffplay fallbacks),
        so there's no Apple-Silicon requirement on the client. Personality
        ranges are validated in TARSPersonality.__post_init__.
        """
        if not self.omlx.server_url.startswith(("http://", "https://")):
            raise ValueError(
                f"OMLX server URL must start with http:// or https://, "
                f"got {self.omlx.server_url!r}"
            )
        if self.omlx.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.omlx.max_tokens}")
        if self.omlx.request_timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.omlx.request_timeout}")
        if self.tts.speed <= 0:
            raise ValueError(f"TTS speed must be positive, got {self.tts.speed}")
        if self.conversation_memory_k <= 0:
            raise ValueError(
                f"conversation_memory_k must be positive, got {self.conversation_memory_k}"
            )
        if self.multi_character_max_tokens <= 0:
            raise ValueError(
                f"multi_character_max_tokens must be positive, "
                f"got {self.multi_character_max_tokens}"
            )
