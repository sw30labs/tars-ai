# Architecture Decision Records

Retrospective ADRs inferred 2026-11-25 from commit c41074a674fd5876fbdc0c6387bb980dac251cd6. See [../assumptions.md](../assumptions.md) for open assumptions.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](./0001-local-omlx-server-for-llm-and-tts.md) | Run both LLM and TTS on a remote/local OMLX server, no in-process models | Accepted, retrospective |
| [0002](./0002-openai-sdk-client-langchain-core-messages.md) | Use the OpenAI Python SDK as the only server client; keep langchain-core for message types | Accepted, retrospective |
| [0003](./0003-tts-description-via-instructions-field.md) | Send the voice description in the OpenAI `instructions` field (via extra_body) as well as `voice` | Accepted, retrospective |
| [0004](./0004-voice-design-per-character-descriptions.md) | Characters get distinct voices from text descriptions, not fixed voice presets | Accepted, retrospective |
| [0005](./0005-personality-knobs-as-prompt-directives.md) | Model TARS personality as four 0-100 knobs converted to tiered prompt directives | Accepted, retrospective |
| [0006](./0006-prompts-externalised-in-yaml.md) | Keep TARS's system prompt and personality scales in prompts.yaml; crew prompts stay in code | Accepted, retrospective |
| [0007](./0007-shared-llm-multi-character-orchestrator.md) | One shared LLM for all characters; orchestrator gives each a persona via system prompt and role mapping | Accepted, retrospective |
| [0008](./0008-buffered-silence-detection.md) | Let guests opt out with a [SILENT] marker, detected on a buffered stream prefix | Accepted, retrospective |
| [0009](./0009-single-pass-followup-for-addressed-characters.md) | Give a directly addressed character exactly one follow-up turn per round | Accepted, retrospective |
| [0010](./0010-rolling-summary-history-trim.md) | Trim history to last K messages and summarise dropped ones with the same LLM | Accepted, retrospective |
| [0011](./0011-rollback-history-on-failed-round.md) | Roll back the user message and partial replies when a round fails | Accepted, retrospective |
| [0012](./0012-command-registry-fast-path.md) | Intercept settings, save/load/history and crew commands before inference via a pluggable registry | Accepted, retrospective |
| [0013](./0013-json-session-persistence-with-name-sanitisation.md) | Persist sessions as JSON files in conversations/ with strict filename-safe names | Accepted, retrospective |
| [0014](./0014-async-tts-synthesis-and-playback-threads.md) | Run TTS synthesis and audio playback in two background daemon threads with queues | Accepted, retrospective |
| [0015](./0015-thinking-disabled-by-default.md) | Disable Qwen hybrid-thinking by default via chat_template_kwargs | Accepted, retrospective |
| [0016](./0016-cli-flags-and-env-vars-with-strix-omlx-naming.md) | Configure by CLI flags with env-var fallbacks matching the strix-omlx convention | Accepted, retrospective |
| [0017](./0017-micromamba-bootstrap-script-and-pinned-requirements.md) | Provide setup_and_run.sh (micromamba) and pin all requirements exactly | Accepted, retrospective |
| [0018](./0018-interstellar-styled-rich-tui.md) | Interstellar-styled terminal UI on a single shared Rich console | Accepted, retrospective |
| [0019](./0019-fakellm-offline-test-suite.md) | Test core logic offline with fake LLMs; no network or TTS in tests | Accepted, retrospective |
