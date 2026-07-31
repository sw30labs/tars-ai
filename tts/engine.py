"""
TARS Voice Synthesis Engine — OMLX audio (Qwen3-TTS Voice Design)

TTS runs on the OMLX server via its OpenAI-compatible `POST /v1/audio/speech`
endpoint — the same server (and OpenAI SDK client) that serves the LLM. TARS's
voice *description* is sent as the OpenAI `voice` field; oMLX maps it to the
model's `instruct` for VoiceDesign TTS models. OMLX returns a WAV, which we play
back locally (sounddevice, with afplay / mpv / ffplay fallbacks).

No local model download — the TTS model lives on OMLX.
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from typing import Optional

from config.settings import TARSConfig

_SENTINEL = None  # poison pill to stop the playback thread


class TARSVoice:
    """
    TARS voice synthesizer — speaks via the OMLX /v1/audio/speech endpoint.

    Qwen3-TTS Voice Design generates a voice from a text description rather than
    a fixed preset, so each character's `voice_desc` becomes a distinct voice.

    Synthesis and playback each run in a background thread: `speak()` returns
    immediately, so one character's TTS round trip overlaps with the next
    character's LLM generation instead of serializing the whole scene.
    """

    def __init__(self, config: TARSConfig):
        from openai import OpenAI

        self.config = config
        # Same OMLX server as the LLM — reuse the OpenAI-compatible client.
        self._client = OpenAI(
            base_url=config.omlx.server_url,
            api_key=config.omlx.api_key,
            timeout=config.omlx.request_timeout,
        )
        self.output_dir = Path(config.audio_output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self._utterance_count = 0

        # Background synthesis queue + thread
        self._synth_queue: queue.Queue[tuple | None] = queue.Queue()
        self._synth_thread = threading.Thread(
            target=self._synth_worker, daemon=True
        )
        self._synth_thread.start()

        # Background playback queue + thread
        self._playback_queue: queue.Queue[tuple[Path, bool] | None] = queue.Queue()
        self._playback_thread = threading.Thread(
            target=self._playback_worker, daemon=True
        )
        self._playback_thread.start()

    def synthesize(
        self,
        text: str,
        voice_desc: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> Optional[Path]:
        """
        Convert text to a WAV via OMLX Qwen3-TTS Voice Design.

        Args:
            text: Text to synthesize.
            voice_desc: Voice description override (defaults to config value).
                        Sent as the OpenAI `voice` field → the model's `instruct`.
            speed: TTS speed override (defaults to config value).

        Returns path to the generated audio file, or None on empty input/output.
        """
        if not text.strip():
            return None

        use_desc = voice_desc or self.config.tts.voice_desc
        if not use_desc:
            raise ValueError(
                "No voice description provided and no default configured. "
                "Pass voice_desc or set config.tts.voice_desc."
            )
        use_speed = speed or self.config.tts.speed
        fmt = self.config.tts.response_format or "wav"

        self._utterance_count += 1

        # OMLX is OpenAI-compatible: POST /v1/audio/speech. Qwen3-TTS VoiceDesign
        # needs the voice *description* in the model's `instruct` kwarg. oMLX's TTS
        # engine only routes that from the request's `instructions` field (the
        # standard OpenAI TTS field) — its `voice` field is routed to the model's
        # `voice` (speaker) param instead, which VoiceDesign ignores. So the
        # description must go in `instructions`. We send it via extra_body for
        # compatibility across openai-python versions, and still pass `voice`
        # (required by the OpenAI schema; VoiceDesign tolerates it).
        resp = self._client.audio.speech.create(
            model=self.config.tts.model,
            voice=use_desc,
            input=text,
            response_format=fmt,
            speed=use_speed,
            extra_body={"instructions": use_desc},
        )

        # Robust across openai-python versions: prefer .content, fall back to .read().
        audio_bytes = getattr(resp, "content", None)
        if audio_bytes is None and hasattr(resp, "read"):
            audio_bytes = resp.read()
        if not audio_bytes:
            return None

        timestamp = int(time.time())
        filename = f"tts_{timestamp}_{self._utterance_count:04d}.{fmt}"
        filepath = self.output_dir / filename
        filepath.write_bytes(audio_bytes)

        return filepath

    def _playback_worker(self) -> None:
        """Background thread: play queued audio files in order."""
        while True:
            item = self._playback_queue.get()
            if item is _SENTINEL:
                break
            audio_path, delete_after = item
            try:
                self._play_blocking(audio_path)
            except Exception as e:
                print(f"  [TARS] Playback error: {e}")
            finally:
                if delete_after:
                    audio_path.unlink(missing_ok=True)
                self._playback_queue.task_done()

    def _play_blocking(self, audio_path: Path) -> None:
        """Play an audio file synchronously (runs inside the worker thread)."""
        if not audio_path.exists():
            return

        try:
            self._play_with_sounddevice(audio_path)
        except Exception:
            self._play_with_system(audio_path)

    def play(self, audio_path: Path, delete_after: bool = False) -> None:
        """
        Enqueue audio for background playback.

        Files play in order without overlap. Returns immediately.
        """
        self._playback_queue.put((audio_path, delete_after))

    def _play_with_sounddevice(self, audio_path: Path) -> None:
        """Play using sounddevice + soundfile (cross-platform). Reads the WAV header."""
        import soundfile as sf
        import sounddevice as sd

        data, samplerate = sf.read(str(audio_path))
        sd.play(data, samplerate)
        sd.wait()

    def _play_with_system(self, audio_path: Path) -> None:
        """Fallback: use a system audio player (afplay on macOS, mpv/ffplay on Linux)."""
        import platform
        import subprocess

        system = platform.system()
        if system == "Darwin":
            subprocess.run(["afplay", str(audio_path)], check=True)
        elif system == "Linux":
            for player in ["mpv", "ffplay", "aplay", "paplay"]:
                try:
                    cmd = [player]
                    if player == "ffplay":
                        cmd.extend(["-nodisp", "-autoexit"])
                    cmd.append(str(audio_path))
                    subprocess.run(cmd, check=True, capture_output=True)
                    return
                except (FileNotFoundError, subprocess.CalledProcessError):
                    continue
            raise RuntimeError("No audio player found. Install mpv or ffplay.")
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

    def _synth_worker(self) -> None:
        """Background thread: synthesize queued utterances, then queue playback."""
        while True:
            item = self._synth_queue.get()
            try:
                if item is _SENTINEL:
                    break
                text, voice_desc, speed, on_synthesized = item
                try:
                    audio_path = self.synthesize(text, voice_desc=voice_desc, speed=speed)
                except Exception as e:
                    print(f"  [TARS] Voice error: {e}")
                    continue
                if audio_path and self.config.play_audio:
                    self.play(audio_path, delete_after=not self.config.save_audio)
                elif audio_path and not self.config.save_audio:
                    audio_path.unlink(missing_ok=True)
                    audio_path = None
                if audio_path and on_synthesized:
                    on_synthesized(audio_path)
            finally:
                self._synth_queue.task_done()

    def speak(
        self,
        text: str,
        voice_desc: Optional[str] = None,
        speed: Optional[float] = None,
        on_synthesized=None,
    ) -> None:
        """
        Full pipeline, fully asynchronous: enqueue for background synthesis,
        then background playback. Returns immediately — the next character's
        LLM generation can start while this utterance is still being synthesized.

        Args:
            text: Text to synthesize.
            voice_desc: Voice description override (defaults to config value).
            speed: TTS speed override (defaults to config value).
            on_synthesized: Optional callback invoked with the audio Path once
                            synthesis succeeds and the file is being kept.
        """
        self._synth_queue.put((text, voice_desc, speed, on_synthesized))

    def wait(self) -> None:
        """Block until all queued synthesis and playback has finished."""
        self._synth_queue.join()
        self._playback_queue.join()

    def cleanup(self) -> None:
        """Wait for synthesis/playback to finish, then remove all generated audio."""
        self.wait()
        for f in self.output_dir.glob("tts_*"):
            f.unlink(missing_ok=True)
