# ADR 0009: Give a directly addressed character exactly one follow-up turn per round

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Turn order is fixed, so a character addressed by a later speaker may already have spoken this round.

## Decision

After the main round, `_find_addressed_characters` selects active characters that already spoke and whose display name appears (case-insensitive substring) in another non-silent response that contains `?`. Those get one follow-up generation; the code comment says one pass max prevents infinite loops.

## Consequences

### Positive

- Questions between characters get answered without runaway loops.

### Negative

- Name matching is substring-based and can mis-trigger (e.g. a name mentioned inside a longer word).
- Only characters that already spoke are eligible.

## Alternatives considered

Open-ended conversation loop between characters; rejected by comment (loop risk).

## Evidence

core/orchestrator.py (generate_round, _find_addressed_characters); tests/test_orchestrator.py (test_followup_when_addressed_with_question).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
