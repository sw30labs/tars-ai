#!/usr/bin/env python3
"""
TARS-AI — Interstellar TARS Voice Agent (OMLX-backed)

Both the LLM and the TTS are served by a local OMLX server (OpenAI-compatible
MLX inference): chat via /v1/chat/completions, voice via /v1/audio/speech.
No cloud. Your prompts and audio never leave the box.
LLM: OMLX (MiniMax-M2 heretic)  |  TTS: OMLX (Qwen3-TTS Voice Design)

Usage:
    python main.py
    python main.py --humor 75 --honesty 90 --no-voice
    python main.py --model MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX
    python main.py --omlx-url http://127.0.0.1:8000/v1 --api-key test
    python main.py --voice-desc "A deep authoritative male voice"
"""

from __future__ import annotations

import argparse
import os
import sys

from rich.markup import escape

from config.settings import TARSConfig, TARSPersonality, OMLXConfig, TTSConfig
from core.agent import TARSAgent
from core.characters import CHARACTER_REGISTRY
from tts.engine import TARSVoice
import ui
from ui import console


# ── CLI Argument Parsing ─────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TARS-AI: Interstellar TARS Voice Agent (MLX Native)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Default settings
  python main.py --humor 100                        # Maximum humor
  python main.py --honesty 95 --no-voice            # Text only, blunt mode
  python main.py --model MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX
  python main.py --omlx-url http://127.0.0.1:8000/v1 --api-key test
  python main.py --voice-desc "A warm British female voice"

The LLM is served by your local OMLX server (OpenAI-compatible MLX). The model
name must match exactly what OMLX serves — see GET {omlx-url}/models or the admin
dashboard at {omlx-url without /v1}/admin/dashboard.

TTS uses Qwen3-TTS Voice Design — voices are generated from text descriptions.
Each character has a built-in voice description. Use --voice-desc to override TARS's default.
        """,
    )

    # Personality
    parser.add_argument("--humor", type=int, default=75, help="Humor level 0-100 (default: 75)")
    parser.add_argument("--honesty", type=int, default=90, help="Honesty level 0-100 (default: 90)")
    parser.add_argument("--discretion", type=int, default=85, help="Discretion level 0-100 (default: 85)")
    parser.add_argument("--trust", type=int, default=70, help="Trust level 0-100 (default: 70)")

    # OMLX LLM server
    parser.add_argument(
        "--model", "--llm", dest="model", type=str,
        default=os.getenv("OMLX_MODEL") or os.getenv("STRIX_LLM")
        or "MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX",
        help="Model id as served by OMLX (default: MiniMax-M2.7-ultra-uncensored-heretic-oQ4-MLX). "
             "Also settable via OMLX_MODEL env var."
    )
    parser.add_argument(
        "--omlx-url", type=str,
        default=os.getenv("OMLX_URL") or os.getenv("LLM_API_BASE") or "http://127.0.0.1:8000/v1",
        help="OMLX server URL (default: http://127.0.0.1:8000/v1). Also OMLX_URL / LLM_API_BASE env."
    )
    parser.add_argument(
        "--api-key", type=str,
        default=os.getenv("OMLX_API_KEY") or os.getenv("LLM_API_KEY") or "test",
        help="OMLX API key, sent as a Bearer token (default: test). Also OMLX_API_KEY / LLM_API_KEY env."
    )
    parser.add_argument("--max-tokens", type=int, default=768, help="Max generation tokens (default: 768)")
    parser.add_argument("--temp", type=float, default=0.7, help="LLM temperature (default: 0.7)")
    parser.add_argument(
        "--timeout", type=float, default=1800.0,
        help="Request timeout in seconds (default: 1800). OMLX loads models on demand, "
             "so the first request after a cold start can be slow."
    )
    parser.add_argument(
        "--thinking", action="store_true",
        help="Enable Qwen hybrid-thinking / chain-of-thought (off by default). "
             "When off, OMLX gets chat_template_kwargs.enable_thinking=false so "
             "replies stay short and TTS-clean."
    )

    # TTS (served by OMLX, same server as the LLM)
    parser.add_argument(
        "--tts-model", type=str,
        default=os.getenv("OMLX_TTS_MODEL") or "Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
        help="TTS model id as served by OMLX (default: Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16). "
             "Also OMLX_TTS_MODEL env."
    )
    parser.add_argument(
        "--voice-desc", type=str,
        default=None,
        help="Voice description for Qwen3-TTS Voice Design "
             "(default: TARS's built-in voice, see core/characters.py)"
    )
    parser.add_argument("--speed", type=float, default=None, help="TTS speed (default: 1.0)")

    # Output
    parser.add_argument("--no-voice", action="store_true", help="Text-only mode, no audio")
    parser.add_argument("--no-save", action="store_true", help="Don't save audio files")

    return parser.parse_args()


# ── Character turn callbacks ─────────────────────────────────────────────

def _on_character_start(indicator: ui.ProcessingIndicator, char) -> None:
    """First non-silent token: kill the PROCESSING readout, print the tag."""
    indicator.stop()
    console.print(ui.name_tag(char) + " ", end="")


def _on_character_end(
    indicator: ui.ProcessingIndicator,
    char,
    text: str,
    agent: TARSAgent,
    voice: TARSVoice | None,
    config: TARSConfig,
) -> None:
    """End of a character's response: newline, tok/s readout, TTS."""
    console.print()  # newline after streaming

    tps = agent.llm.last_generation_tps
    if tps > 0:
        ui.tps_readout(tps)

    # Speak with the character's voice — synthesis runs in the background so
    # the next character's LLM generation starts immediately. Errors are
    # reported by the synthesis worker.
    if voice:
        voice.speak(
            text,
            voice_desc=char.voice_desc,
            speed=char.speed,
            on_synthesized=(
                (lambda p: console.print(f"\n  [dim]Audio: {p}[/dim]"))
                if config.save_audio else None
            ),
        )

    # Another character may be up next — bring the readout back until they
    # start streaming (stopped again in _on_character_start / after the round).
    indicator.start()


# ── Main Loop ────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Build config from CLI args
    personality = TARSPersonality(
        humor=args.humor,
        honesty=args.honesty,
        discretion=args.discretion,
        trust=args.trust,
    )

    omlx_config = OMLXConfig(
        model=args.model,
        server_url=args.omlx_url,
        api_key=args.api_key,
        max_tokens=args.max_tokens,
        temperature=args.temp,
        request_timeout=args.timeout,
        enable_thinking=args.thinking,
    )

    tts_config = TTSConfig(model=args.tts_model)

    config = TARSConfig(
        personality=personality,
        omlx=omlx_config,
        tts=tts_config,
        play_audio=not args.no_voice,
        save_audio=not args.no_save,
    )

    # CLI voice overrides apply to TARS's character entry — the per-character
    # registry values are what actually reach the synthesizer.
    if args.voice_desc:
        CHARACTER_REGISTRY["tars"].voice_desc = args.voice_desc
        config.tts.voice_desc = args.voice_desc  # fallback for desc-less calls
    if args.speed is not None:
        CHARACTER_REGISTRY["tars"].speed = args.speed
        config.tts.speed = args.speed

    # Validate
    try:
        config.validate()
    except ValueError as e:
        ui.alert(f"Configuration error: {e}")
        sys.exit(1)

    # Boot — USMC field reactivation sequence
    ui.print_boot(config)

    # Initialize LLM (OMLX client — the connection is lazy; the model loads on
    # the first chat, so that request can be slow after a cold start).
    ui.dim(f"Establishing uplink to OMLX @ {config.omlx.server_url} ...")
    try:
        agent = TARSAgent(config)
        ui.ok("OMLX uplink established")
        ui.dim(f"'{config.omlx.model}' loads on demand — first reply may be slow.")
        console.print()
    except Exception as e:
        ui.alert(f"Uplink failed: {e}")
        ui.dim(f"Ensure OMLX is running and serving '{config.omlx.model}'.")
        ui.dim(f"Dashboard: {config.omlx.dashboard_url}")
        sys.exit(1)

    # Initialize TTS (OMLX audio client — synthesis happens on the OMLX server)
    voice: TARSVoice | None = None
    if not args.no_voice:
        try:
            voice = TARSVoice(config)
        except Exception as e:
            ui.warn(f"Voice init failed: {e}")
            ui.warn("Falling back to text-only mode.")
            voice = None

    indicator = ui.ProcessingIndicator()

    # Conversation loop
    while True:
        try:
            user_input = console.input(ui.prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            ui.say_tars("See you on the other side, Cooper.")
            if voice:
                voice.wait()
            agent.save_conversation("autosave")
            break

        if not user_input:
            continue

        # Meta commands
        if user_input.lower() in ("quit", "exit", "q"):
            ui.say_tars("Don't let me leave, Murph.")
            if voice:
                voice.wait()
            agent.save_conversation("autosave")
            break

        if user_input.lower() == "reset":
            agent.reset()
            ui.say_tars("Memory cleared. Starting fresh.")
            continue

        if user_input.lower() == "cleanup":
            if voice:
                voice.cleanup()
            ui.say_tars("Audio files purged.")
            continue

        # Check for registered commands (settings, persistence, character management)
        cmd_response = agent.registry.dispatch(
            user_input, agent.config, agent._command_context()
        )
        if cmd_response:
            console.print(f"{ui.tars_tag()} {cmd_response}")
            console.print()
            continue

        # Multi-character generation round
        indicator.start()
        try:
            responses = agent.orchestrator.generate_round(
                user_input,
                on_character_start=lambda char: _on_character_start(indicator, char),
                on_character_token=lambda cid, tok: console.print(
                    escape(tok), end="", highlight=False
                ),
                on_character_end=lambda char, text: _on_character_end(
                    indicator, char, text, agent, voice, config
                ),
            )

            # If all characters were silent (shouldn't happen since TARS never is)
            if all(r.silent for r in responses):
                console.print(f"[{ui.STYLE_DIM}]...[/{ui.STYLE_DIM}]")

        except Exception as e:
            console.print()
            ui.alert(str(e))
            continue
        finally:
            indicator.stop()

        console.print()


if __name__ == "__main__":
    main()
