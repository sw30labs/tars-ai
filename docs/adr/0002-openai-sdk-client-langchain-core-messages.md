# ADR 0002: Use the OpenAI Python SDK as the only server client; keep langchain-core for message types

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

OMLX exposes an OpenAI-compatible API. The code needs a chat client and an audio client, and a conversation history representation.

## Decision

`OMLXLLM` (core/agent.py) and `TARSVoice` (tts/engine.py) each build an `openai.OpenAI(base_url, api_key, timeout)` client. LangChain is used only for `BaseMessage`/`HumanMessage`/`AIMessage`/`SystemMessage` types; `_format_messages` converts them to OpenAI-style dicts. No LangChain chat model or chains are used.

## Consequences

### Positive

- One client library for both chat and TTS; swapping the server is a URL change.
- Message types serialise easily (see ADR 0013).

### Negative

- `langchain-core` is a dependency used only for four message classes.
- `_format_messages` silently drops message types other than System/Human/AI.

## Alternatives considered

Direct `requests`/`httpx` calls; full LangChain chat model wrapper. Neither is present in code; why they were not chosen is not documented (A-002).

## Evidence

core/agent.py (`_format_messages`, `OMLXLLM`); tts/engine.py; requirements.txt (openai, langchain-core).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
