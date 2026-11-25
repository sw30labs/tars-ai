# ADR 0001: Run both LLM and TTS on a remote/local OMLX server, no in-process models

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

TARS-AI is a CLI voice agent. Commit ab32516 (2026-07-06) is titled "Run entirely on local OMLX server (LLM + TTS)". README and CLAUDE.md state that nothing goes to a cloud API and nothing is downloaded to the client; both models live on the OMLX box and the client only plays audio.

## Decision

All inference goes to an OMLX server (OpenAI-compatible MLX inference server, default `http://127.0.0.1:8000/v1`): chat via `/v1/chat/completions`, speech via `/v1/audio/speech`. There is no in-process mlx-lm or mlx-audio path (CLAUDE.md: "there is no in-process mlx-lm or mlx-audio path"). `TARSConfig.validate()` no longer enforces Apple Silicon.

## Consequences

### Positive

- Client runs on any OS that can reach the server; Apple Silicon only needed on the OMLX host.
- Prompts and audio stay on the user's own hardware (README: no cloud APIs).
- No model weights downloaded or held by the client.

### Negative

- Hard runtime dependency on a running OMLX server (v0.3.0+ for `/v1/audio/speech`, per README).
- Model ids must match `GET /v1/models` exactly or the server returns 404.
- First request after cold start can take minutes because OMLX loads models on demand (hence the 1800 s timeout, see ADR 0016).

## Alternatives considered

In-process mlx-lm / mlx-audio on the client (apparently the earlier approach; inferred from the commit title and README wording, see A-001). Cloud APIs are explicitly rejected in README.

## Evidence

README.md; CLAUDE.md (Project Overview, OMLX backend); config/settings.py (OMLXConfig, TARSConfig.validate); core/agent.py; tts/engine.py; commit ab32516.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
