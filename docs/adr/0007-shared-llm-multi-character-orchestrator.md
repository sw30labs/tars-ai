# ADR 0007: One shared LLM for all characters; orchestrator gives each a persona via system prompt and role mapping

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

The agent supports multi-party scenes with TARS, Brand, Dr. Mann, Prof. Brand and Murphy.

## Decision

`ConversationOrchestrator` keeps one shared history (`self.messages`), a list of active character ids (TARS always first, always present), and calls the same `OMLXLLM` once per active character per round. `_build_messages_for_character` builds a per-character view: system prompt (TARS dynamic prompt plus multi-party addendum when guests present, or the guest's prompt), a "[Present in this conversation ...]" line, optional summary, then history where the character's own turns are `assistant` and everything else is `user` with a `Name: ` prefix. Guests are capped at `min(character.max_tokens, multi_character_max_tokens=256)`; TARS gets 768. Call/dismiss/who/everyone management is on the orchestrator.

## Consequences

### Positive

- Only one model needed; adding a character is a registry entry.
- Role mapping respects the system/user/assistant limit the code comments call "critical".

### Negative

- Characters are sequential (latency scales with number of active characters).
- Persona consistency relies entirely on prompts.

## Alternatives considered

Separate model per character, or a single call that scripts all characters; not present in code.

## Evidence

core/orchestrator.py; core/characters.py; config/settings.py (multi_character_max_tokens); tests/test_orchestrator.py (guest token cap, role mapping).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
