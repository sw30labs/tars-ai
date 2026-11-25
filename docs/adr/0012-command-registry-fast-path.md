# ADR 0012: Intercept settings, save/load/history and crew commands before inference via a pluggable registry

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Some user inputs (set humor to 50, call brand) do not need the LLM and should respond instantly and deterministically.

## Decision

`CommandRegistry` holds `Command`s (name, patterns as substring or compiled regex, handler). `dispatch` lowercases input, checks commands in registration order and returns the first non-None handler result. The agent registers settings, persistence and character commands. main.py dispatches before the orchestrator, after hard-coded meta commands (quit/exit/q, reset, cleanup). Call verbs deliberately exclude generic verbs like "get" (test_get_is_not_a_call_verb). Handler output goes through `rich.markup.escape` for unknown names.

## Consequences

### Positive

- Instant, in-character responses with no tokens spent.
- New commands are added by registering a `Command`.

### Negative

- Substring and regex matching can intercept ordinary chat (e.g. any text containing "status report" or starting with "save").
- Meta commands exist in two places (main.py hard-coded vs registry).

## Alternatives considered

LLM tool/function calling for settings and crew management; not used in code.

## Evidence

core/commands.py; core/character_commands.py; core/agent.py; main.py; tests/test_commands.py; tests/test_ui.py.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
