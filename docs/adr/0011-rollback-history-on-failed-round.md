# ADR 0011: Roll back the user message and partial replies when a round fails

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

An exception mid-round (e.g. OMLX down) could leave an unanswered user message or partial scene in history.

## Decision

`generate_round` records `history_len` after appending the user's message; on any exception it truncates `messages` back and pops the trailing user message, then re-raises. main.py catches and shows an alert. Responses are committed to history only after the main round and follow-up round each finish.

## Consequences

### Positive

- Retry after failure sees a clean history.

### Negative

- Partially generated and spoken output is discarded from history even if already printed or queued to TTS.

## Alternatives considered

Keep partial history; not chosen per tests.

## Evidence

core/orchestrator.py generate_round; tests/test_orchestrator.py (test_failed_round_rolls_back_history, ..._partial_commits); main.py exception handling.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
