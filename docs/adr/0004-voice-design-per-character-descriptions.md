# ADR 0004: Characters get distinct voices from text descriptions, not fixed voice presets

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Qwen3-TTS Voice Design builds voices from descriptions. The agent supports TARS plus four Interstellar crew guests.

## Decision

Each `Character` carries `voice_desc` and `speed`. `TARS_VOICE_DESC` in core/characters.py is the canonical TARS voice; CLI `--voice-desc` and `--speed` overwrite TARS's registry entry at startup (main.py). `TTSConfig.voice_desc` is only a fallback for description-less calls; if neither exists `synthesize` raises ValueError.

## Consequences

### Positive

- Guests (Brand, Dr. Mann, Prof. Brand, Murphy) sound distinct with no extra models.
- Single source of truth for TARS's voice.

### Negative

- Voice consistency depends on the TTS model's interpretation of prose descriptions; not tested (tests use no TTS).
- CLI overrides mutate the module-level `CHARACTER_REGISTRY` global.

## Alternatives considered

Fixed speaker presets (README contrasts these with VoiceDesign).

## Evidence

core/characters.py; main.py (voice overrides); tts/engine.py `synthesize`; README.md Voice section.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
