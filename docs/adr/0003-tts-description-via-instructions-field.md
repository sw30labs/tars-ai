# ADR 0003: Send the voice description in the OpenAI `instructions` field (via extra_body) as well as `voice`

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Qwen3-TTS VoiceDesign generates a voice from a text description. The comment in tts/engine.py states oMLX routes the request's `instructions` field to the model's `instruct` kwarg, while its `voice` field is routed to the speaker parameter, which VoiceDesign ignores.

## Decision

`TARSVoice.synthesize` calls `audio.speech.create(model, voice=use_desc, input, response_format, speed, extra_body={"instructions": use_desc})`. The description is sent in both fields: `voice` because the OpenAI schema requires it, `instructions` because that is what works. `extra_body` is used for compatibility across openai-python versions.

## Consequences

### Positive

- Distinct voices per character actually take effect on oMLX.
- Works across openai-python versions.

### Negative

- Behaviour depends on oMLX internals described only in a code comment; a server change could break it silently.
- Docstrings in tts/engine.py (module header, `synthesize`), config/settings.py (`TTSConfig`) and the README still say the description goes in `voice` only, which contradicts the code (A-003).

## Alternatives considered

Sending the description only in `voice` (the earlier documented behaviour; rejected per the code comment because VoiceDesign ignores it).

## Evidence

tts/engine.py lines 97-112; CLAUDE.md (TTS voice bullet); config/settings.py TTSConfig docstring; README.md Voice section.

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
