# ADR 0019: Test core logic offline with fake LLMs; no network or TTS in tests

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Commit 5d2bfbe added the test suite; README claims 59 unit tests (not verified here, A-011).

## Decision

Tests (pytest) cover commands, orchestrator, persistence, settings and ui. The orchestrator tests use `FakeLLM`/`BoomLLM`/`PartialLLM` stand-ins passed in place of `OMLXLLM`, and `conftest.py` only ensures repo root is on sys.path. Persistence tests monkeypatch `CONVERSATIONS_DIR` to `tmp_path`. No test touches `OMLXLLM`, `TARSVoice`, or `main.py`, and no CI workflow exists in the repo.

## Consequences

### Positive

- Fast, deterministic tests with no server.

### Negative

- Network adapters (`OMLXLLM`, `TARSVoice`), `_trim_history`/summarisation and `main.py` are untested.
- No CI.

## Alternatives considered

Integration tests against a live OMLX; not present.

## Evidence

tests/*.py; conftest.py; README.md Tests section.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
