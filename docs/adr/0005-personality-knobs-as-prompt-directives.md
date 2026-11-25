# ADR 0005: Model TARS personality as four 0-100 knobs converted to tiered prompt directives

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

The Interstellar TARS has adjustable humor/honesty/discretion/trust settings. The agent should expose them and let the user change them mid-conversation.

## Decision

`TARSPersonality` holds humor (75), honesty (90), discretion (85), trust (70), validated 0-100 in `__post_init__`. `to_prompt_block()` walks tiers from `prompts.yaml` `personality_scales` (first tier whose `min` is <= value wins) for humor, honesty and discretion only. `summary()` (which includes trust) is injected into the system prompt. Settings can be changed at runtime with natural-language commands (ADR 0012), which rebuild the system prompt.

## Consequences

### Positive

- Behaviour can be tuned without code changes by editing YAML tiers.
- Validation rejects out-of-range values in CLI and runtime paths.

### Negative

- Trust has no directive tier, so changing it only changes the displayed summary line and the canned acknowledgement text, not a dedicated instruction (A-004).
- Tier thresholds are coarse (3-4 tiers per knob).

## Alternatives considered

Free-text personality prompt; per-knob continuous interpolation. Neither is in the code.

## Evidence

config/settings.py (TARSPersonality); prompts.yaml (personality_scales); core/prompt.py; core/commands.py (settings_adjust); tests/test_settings.py.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
