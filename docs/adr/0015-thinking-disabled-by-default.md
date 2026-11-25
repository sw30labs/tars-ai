# ADR 0015: Disable Qwen hybrid-thinking by default via chat_template_kwargs

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Commit 5d2bfbe (2026-07-31, "Disable Qwen thinking by default; TUI, async TTS, and test suite."). Code comments say Qwen3/3.5/3.6 hybrid-thinking models think out loud on OMLX, dumping reasoning into replies and TTS.

## Decision

`OMLXConfig.enable_thinking=False`; every chat request sends `extra_body={"chat_template_kwargs": {"enable_thinking": <bool>}}` (a top-level `enable_thinking` is ignored by OMLX, per comment, referencing jundot/omlx issue 1378). CLI `--thinking` re-enables it.

## Consequences

### Positive

- Short, TTS-clean replies.

### Negative

- Lower reasoning quality for hard questions unless `--thinking` is passed.
- Parameter is sent even to models that do not use it (the default MiniMax model); behaviour on such models is not documented (A-006).

## Alternatives considered

Strip reasoning text client-side; not present.

## Evidence

config/settings.py (OMLXConfig); core/agent.py (OMLXLLM.generate); main.py (--thinking); commit 5d2bfbe.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
