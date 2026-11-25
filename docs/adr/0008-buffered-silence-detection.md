# ADR 0008: Let guests opt out with a [SILENT] marker, detected on a buffered stream prefix

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Guests should not speak every turn; the LLM streams tokens and the UI prints as they arrive.

## Decision

Guest prompts instruct: reply exactly `[SILENT]` when nothing to add. `_generate_character_response` buffers the first `SILENCE_BUFFER_SIZE` (20) characters before printing. `_is_silent` accepts a set of markers or the regex `^\[?\s*silent\s*\]?\.?\s*$`. Silent replies are not committed to history and not spoken; if a stream ends before 20 chars and is not silent, the buffer is flushed at the end.

## Consequences

### Positive

- Silent guests produce no output or audio.
- Silent replies do not pollute history.

### Negative

- Streaming of non-silent guests starts only after 20 characters (small delay).
- A bare word `silent` is treated as silent (tests assert this), which could swallow a legitimate one-word reply.

## Alternatives considered

Non-streaming generation before display; a separate routing call to decide who speaks. Neither is in code.

## Evidence

core/orchestrator.py (SILENCE_MARKERS, SILENCE_BUFFER_SIZE, _is_silent); core/characters.py prompts; tests/test_orchestrator.py (test_is_silent, test_silent_guest_not_committed).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
