# ADR 0013: Persist sessions as JSON files in conversations/ with strict filename-safe names

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Users can save, load and list conversations; session names become filenames.

## Decision

`core/persistence.py` writes `conversations/<name>.json` (repo-relative) containing name, UTC saved_at, message_count, context_summary, personality, messages (role, content, optional name) and active_characters. Names must match `^[\w\- ]+$`; anything else (separators, dots) is rejected to prevent path traversal. Loading restores messages, summary, active characters and personality, then rebuilds the system prompt. On quit/EOF main.py saves a session named `autosave`.

## Consequences

### Positive

- Path traversal prevented (tests cover `../../etc/passwd`, `..`, `a/b`).
- Personality and crew roster travel with the session.
- `conversations/` is gitignored.

### Negative

- Plaintext JSON on disk; the single `autosave` name is overwritten each exit and is not auto-loaded.
- `list_conversations` silently skips corrupt files.

## Alternatives considered

A database or per-user directory; not present.

## Evidence

core/persistence.py; core/agent.py (save/load); main.py (autosave); .gitignore; tests/test_persistence.py.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
