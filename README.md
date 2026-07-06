# TARS-AI — Interstellar TARS Voice Agent (OMLX-backed)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![OMLX](https://img.shields.io/badge/LLM%2BTTS-OMLX%20server-FF6F00)
![Server](https://img.shields.io/badge/OMLX%20host-Apple%20Silicon-000000?logo=apple&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1C3C3C)
![License](https://img.shields.io/badge/License-MIT-green)
![Local Only](https://img.shields.io/badge/Cloud-None%20%7C%20Fully%20Local-blue)

> "Everybody good? Plenty of slaves for my robot colony?" — TARS

<img src="images/1.png" width="60%" />

A LangGraph-powered conversational AI that embodies TARS from Interstellar.
Text in, TARS voice out. Both the LLM **and** the TTS run on your local **OMLX**
server (an OpenAI-compatible MLX inference server) — the LLM via
`/v1/chat/completions`, the voice via `/v1/audio/speech`. No cloud APIs, and
nothing downloads to the client: both models live on your OMLX box.

## Architecture

```
┌───────────────────────────────────────────────────────┐
│                      TARS-AI CLI                      │
├───────────────────────────────────────────────────────┤
│                 LangGraph Agent Graph                 │
│  ┌────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │ Personality →   LLM Node     →   Voice Output   │  │
│  │  Injector  │  │ OpenAI SDK  │  │  OpenAI SDK    │  │
│  └────────────┘  └──────┬──────┘  └───────┬────────┘  │
└─────────────────────────┼─────────────────┼───────────┘
   /v1/chat/completions   │                 │  /v1/audio/speech
                          ▼                 ▼
        ┌─────────────────────────────────────────┐
        │   OMLX server  http://127.0.0.1:8000    │
        │   LLM:  MiniMax-M2.7 heretic (MLX)      │
        │   TTS:  Qwen3-TTS VoiceDesign (MLX)     │
        │   dashboard: /admin/dashboard           │
        └─────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Have an OMLX server running and serving your model
#    (dashboard at http://127.0.0.1:8000/admin/dashboard)

# 2. Install dependencies (Apple Silicon needed for voice; text-only runs anywhere)
pip install -r requirements.txt

# 3. Run TARS (talks to OMLX at 127.0.0.1:8000; TTS model downloads on first launch)
python main.py

# Custom personality
python main.py --humor 100 --honesty 95

# Text-only mode (no TTS)
python main.py --no-voice

# Point at a specific model / endpoint / key
python main.py --model MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX
python main.py --omlx-url http://127.0.0.1:8000/v1 --api-key test

# Different voice
python main.py --voice-desc "A warm British female voice" --speed 0.88
```

> **Note:** OMLX loads models on demand, so the *first* reply after a cold start
> can be slow while the model loads into memory. Watch progress on the dashboard.

## TARS Personality Settings

| Setting     | Default | Description                              |
|-------------|---------|------------------------------------------|
| humor       | 75%     | Dry wit and sarcasm level                |
| honesty     | 90%     | Directness vs diplomatic filtering       |
| discretion  | 85%     | Information sharing restraint            |
| trust       | 70%     | Willingness to follow unusual orders     |

Adjust at runtime: `Set humor to 50` or `Adjust honesty to 95`

## Voice

TTS is served by OMLX via `POST /v1/audio/speech` using **Qwen3-TTS Voice
Design** — voices are generated from a text *description* rather than fixed
presets. TARS's description is sent as the OpenAI `instructions` field, which
oMLX routes to the model's `instruct`. TARS's default:

> "A deep, measured, authoritative American male voice. Military precision.
> Deliberate pauses."

Override it with `--voice-desc "..."`. Each crew character carries its own voice
description, so summoned guests (Brand, Dr. Mann, Prof. Brand, Murphy) sound distinct.

## Configuration

The LLM endpoint is configurable by flag or environment variable (env names match
the [strix-omlx](https://github.com/sw30labs/strix-omlx) convention):

| Flag          | Env var                        | Default                                          |
|---------------|--------------------------------|--------------------------------------------------|
| `--model`     | `OMLX_MODEL` / `STRIX_LLM`     | `MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX`  |
| `--tts-model` | `OMLX_TTS_MODEL`               | `Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`           |
| `--omlx-url`  | `OMLX_URL` / `LLM_API_BASE`    | `http://127.0.0.1:8000/v1`                       |
| `--api-key`   | `OMLX_API_KEY` / `LLM_API_KEY` | `test`                                           |
| `--voice-desc`| —                              | TARS's default voice description                 |
| `--timeout`   | —                              | `1800` (seconds; covers on-demand model load)    |

## Models

| Component | Default                                       | Where it runs |
|-----------|-----------------------------------------------|---------------|
| LLM       | MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX | OMLX server   |
| TTS       | Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16          | OMLX server   |

Both must already be served by your OMLX server — the ids you pass must match
`GET {omlx-url}/models` exactly, or the server returns a 404. Nothing downloads to
the client; both models' RAM footprints live on the OMLX box. (TTS needs oMLX
v0.3.0+, which added the `/v1/audio/speech` endpoint.)

## Requirements

- A running **OMLX** server (v0.3.0+) serving both the LLM and a Qwen3-TTS model.
- Python 3.10+ on the client — **any OS**; no MLX / Apple Silicon needed client-side.
- For audio: a working output device (`sounddevice`, or `afplay`/`mpv`/`ffplay`). Use `--no-voice` to skip.
