# ADR 0006: Keep TARS's system prompt and personality scales in prompts.yaml; crew prompts stay in code

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

The TARS system prompt is long and tuned; crew prompts are also long.

## Decision

`prompts.yaml` holds `system_prompt` (a `str.format` template with `{personality_summary}` and `{personality_directives}`) and `personality_scales`. It is loaded once with `functools.lru_cache` by `_load_prompts()`, resolved relative to the repo root. Guest character prompts and `TARS_MULTI_PARTY_ADDENDUM` are Python string constants in core/characters.py. The TARS registry entry has `system_prompt=""` because it is built dynamically.

## Consequences

### Positive

- TARS prompt/tiers editable without touching Python.
- Cached load keeps prompt rebuilds cheap.

### Negative

- Prompt content is split across two places (YAML for TARS, Python for guests), and a stray `{` in the template would break `str.format`.
- lru_cache means edits need a restart.

## Alternatives considered

All prompts in code or all in YAML; the code does not say why they were split (A-005).

## Evidence

prompts.yaml; config/settings.py `_load_prompts`; core/prompt.py; core/characters.py.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
