# ADR 0018: Interstellar-styled terminal UI on a single shared Rich console

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Commit 5d2bfbe added a TUI. ui.py documents the aesthetic: USMC reactivation boot scroll, segmented parameter bars, Endurance console palette.

## Decision

All output goes through one `rich.console.Console`. Boot sequence (`print_boot`) prints diagnostics including OMLX URL/model/TTS model, wordmark, ASCII monolith, parameter bars and a command reference panel. `ProcessingIndicator` (Rich status spinner) runs while the LLM generates and is stopped on first non-silent token. Dynamic text (exceptions, user input, model tokens) is passed through `escape()`; tests cover bracket-laden messages.

## Consequences

### Positive

- Single console avoids live-display conflicts with streaming tokens.
- Markup injection from user/model text is neutralised.

### Negative

- Boot sequence adds several seconds of deliberate `time.sleep` delays.
- Wordmark and CLI description still say "MLX Native" although inference is remote (A-010).

## Alternatives considered

Plain print output; not chosen.

## Evidence

ui.py; main.py; tests/test_ui.py.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
