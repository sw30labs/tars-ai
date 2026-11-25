# ADR 0014: Run TTS synthesis and audio playback in two background daemon threads with queues

## Status

Accepted, retrospective, inferred 2026-11-25

## Context

Each character's TTS round trip would otherwise serialise the scene with the next character's LLM generation.

## Decision

`TARSVoice.speak()` enqueues on a synthesis queue and returns immediately. A synth worker calls `/v1/audio/speech`, writes a WAV (`tts_<unix>_<n>.wav`) into `audio_output/`, and enqueues playback; a playback worker plays files in order (sounddevice + soundfile, falling back to afplay on macOS or mpv/ffplay/aplay/paplay on Linux). `wait()` joins both queues (used at quit); `cleanup` deletes `tts_*` files. Errors are printed by the worker and do not stop the loop. `--no-save` deletes files after playback.

## Consequences

### Positive

- Next character's generation overlaps with prior speech synthesis.
- Playback order preserved without overlap.

### Negative

- `audio_output_dir` is relative to the current working directory, unlike conversations/ which is repo-relative (A-014).
- Daemon threads: pending audio is lost if the process exits without `wait()`.
- Not covered by tests.

## Alternatives considered

Synchronous synth+play; not chosen per code comments.

## Evidence

tts/engine.py; main.py (_on_character_end, wait/cleanup); config/settings.py (play_audio, save_audio); .gitignore (audio_output/).

Reviewed at commit c41074a674fd5876fbdc0c6387bb980dac251cd6. Rationale not stated in the repository is labelled "inferred" and tracked in [../assumptions.md](../assumptions.md).
