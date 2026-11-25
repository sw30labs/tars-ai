# ADR 0010: Trim history to last K messages and summarise dropped ones with the same LLM

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Context grows unbounded in a long conversation.

## Decision

`conversation_memory_k` (default 20) caps `messages`. When exceeded, dropped messages are summarised by `_summarize_context` (an LLM call with a fixed concise-summarizer system prompt, asking for 2-3 sentences) merged with any existing summary; the summary is injected as a SystemMessage in each character's view and is persisted with saved sessions.

## Consequences

### Positive

- Long sessions stay within context while retaining topics.

### Negative

- Summarisation adds an extra blocking LLM call after the round when trimming occurs, using the same model and default `max_tokens`.
- Summary quality unverified; no test covers `_trim_history`.
- Summarisation failure would raise inside `generate_round` after responses were committed.

## Alternatives considered

Plain truncation without summary; larger window. Not chosen per code, rationale for K=20 not documented (A-007).

## Evidence

core/orchestrator.py (_trim_history, _summarize_context); config/settings.py (conversation_memory_k); core/persistence.py (context_summary).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
