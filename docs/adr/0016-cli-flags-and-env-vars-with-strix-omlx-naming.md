# ADR 0016: Configure by CLI flags with env-var fallbacks matching the strix-omlx convention

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

The same client should point at different OMLX servers/models without code changes.

## Decision

main.py reads `--model`/`--llm` (env `OMLX_MODEL` or `STRIX_LLM`), `--omlx-url` (`OMLX_URL` or `LLM_API_BASE`), `--api-key` (`OMLX_API_KEY` or `LLM_API_KEY`, default `test` sent as Bearer), `--tts-model` (`OMLX_TTS_MODEL`), `--timeout` (default 1800 s to cover on-demand model load), `--max-tokens` 768, `--temp` 0.7, `--thinking`, `--voice-desc`, `--speed`, `--no-voice`, `--no-save`. Defaults: LLM `MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX`, TTS `Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`. `TARSConfig.validate()` checks URL scheme and positivity of numeric values.

## Consequences

### Positive

- Reuses env names from the user's strix-omlx project.
- Misconfiguration fails early with a clear alert and exit 1.

### Negative

- Default API key `test` and plain http assume a trusted local network.
- Defaults are repeated in main.py, settings.py and setup_and_run.sh, and the script's default LLM differs (A-008).

## Alternatives considered

Config file; not present.

## Evidence

main.py; config/settings.py; README.md Configuration table; setup_and_run.sh.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
