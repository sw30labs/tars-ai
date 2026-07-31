# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TARS-AI is a conversational AI agent embodying TARS from Interstellar. Both the LLM and the TTS run on a local **OMLX** server — an OpenAI-compatible MLX inference server — reached via the OpenAI SDK. The LLM uses `/v1/chat/completions`; text-to-speech (Qwen3-TTS Voice Design) uses `/v1/audio/speech`. Nothing goes to a cloud API, and nothing is downloaded to the client: both models live on your OMLX box. The client only does audio playback.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run with defaults (talks to OMLX at http://127.0.0.1:8000/v1)
python main.py

# Run text-only (no TTS — works off Apple Silicon too)
python main.py --no-voice

# Run with custom personality
python main.py --humor 100 --honesty 95

# Point at a specific model OMLX serves (must match GET /v1/models exactly)
python main.py --model MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX

# Custom OMLX endpoint / key
python main.py --omlx-url http://127.0.0.1:8000/v1 --api-key test

# Different TTS voice/speed
python main.py --voice-desc "A warm British female voice" --speed 0.88

# Or use env vars (compatible with the strix-omlx naming)
OMLX_URL=http://127.0.0.1:8000/v1 OMLX_API_KEY=test OMLX_MODEL=MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX python main.py
# Run the test suite
pytest
```

There is no lint command configured.

## Architecture

```
main.py                  CLI entry point, conversation loop, character turn callbacks
ui.py                    Interstellar-faithful TUI: boot reactivation scroll, parameter bars,
                         monolith figure, HUD tags, PROCESSING indicator, alerts
config/settings.py       Dataclasses: TARSPersonality, OMLXConfig, TTSConfig, TARSConfig
core/agent.py            TARSAgent facade (LLM + orchestrator + command registry) + OMLXLLM (OpenAI SDK -> OMLX server)
core/orchestrator.py     ConversationOrchestrator - multi-character (crew) turn-taking
core/prompt.py           build_tars_system_prompt() - dynamic system prompt from personality knobs
core/characters.py       Crew character registry (prompts, voices) + TARS_VOICE_DESC canonical default
tts/engine.py            TARSVoice - OMLX /v1/audio/speech synthesis, playback, audio files
tests/                   pytest suite (commands, orchestrator, persistence, settings)
```

### Data Flow

User input → command registry dispatch (settings/save/crew fast path) or `ConversationOrchestrator.generate_round()` → per character: `OMLXLLM.generate()` (streaming chat completions against the OMLX `/v1` endpoint via the OpenAI SDK) → response text to console → `TARSVoice.speak()` (if enabled; background synthesis thread) → `POST /v1/audio/speech` on OMLX → WAV bytes → play via sounddevice/afplay (background playback thread)

### OMLX backend (LLM + TTS)

- Both models run on the OMLX server; there is no in-process mlx-lm or mlx-audio path. The client is pure OpenAI SDK.
- `OMLXLLM` (`core/agent.py`) calls `/v1/chat/completions`. `TARSVoice` (`tts/engine.py`) calls `/v1/audio/speech`. Both share the same `openai.OpenAI(base_url=<omlx>/v1, api_key=<key>)` wiring; the key is sent as `Authorization: Bearer <key>` (default `test`).
- **TTS voice**: TARS's `voice_desc` is sent as the OpenAI **`instructions`** field (via `extra_body`). oMLX routes `instructions` → the model's `instruct` kwarg, which is what Qwen3-TTS **VoiceDesign** uses to drive the voice. (The `voice` field is routed to the model's speaker param, which VoiceDesign ignores, so the description must go in `instructions`.) OMLX returns WAV.
- `OMLXConfig.model` and `TTSConfig.model` **must** match ids OMLX actually serves — not HuggingFace paths. Check `GET {server_url}/models` or the dashboard at `{server_url without /v1}/admin/dashboard`.
- OMLX loads models on demand, so the first request after a cold start can take minutes. The client uses a generous `request_timeout` (default 1800s).

### Key Patterns

- **Personality-as-prompt**: Four knobs (humor, honesty, discretion, trust, each 0-100) are converted to prompt directives via `TARSPersonality.to_prompt_block()` and injected into the system prompt. Adjustable at runtime via natural language commands in `core/commands.py`.
- **TTS is remote**: synthesis happens on OMLX. `TARSVoice` sends text + voice description to `/v1/audio/speech` and plays back the returned WAV. No local model, no download.
- **Conversation memory**: message history lives in the `ConversationOrchestrator` and is trimmed to the last K messages (default 20) with rolling summarization of what's dropped. The system prompt is always preserved.
- **Multi-character crew**: `ConversationOrchestrator` runs turn-taking across Interstellar crew characters, each a different system prompt + voice description (its own `/v1/audio/speech` voice), all served by the same OMLX models. Guest characters can stay `[SILENT]`.
- **Settings fast path**: commands like "set humor to 50" or "what are your settings?" are intercepted before inference.

### Platform Constraint

None on the client. Both the LLM and TTS run on OMLX, and audio playback is cross-platform (sounddevice, with afplay / mpv / ffplay fallbacks), so TARS can run from any OS that can reach the OMLX server. `TARSConfig.validate()` no longer enforces Apple Silicon. (The OMLX server itself is macOS/Apple Silicon.)

### Defaults

- **LLM (OMLX)**: `MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX`
- **TTS (OMLX)**: `Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`
- **Endpoint**: `http://127.0.0.1:8000/v1`, key `test`
