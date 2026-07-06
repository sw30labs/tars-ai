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
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from config.settings import TARSConfig, TARSPersonality, OMLXConfig, TTSConfig
from core.agent import TARSAgent
from tts.engine import TARSVoice


console = Console()


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

    # TTS (served by OMLX, same server as the LLM)
    parser.add_argument(
        "--tts-model", type=str,
        default=os.getenv("OMLX_TTS_MODEL") or "Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16",
        help="TTS model id as served by OMLX (default: Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16). "
             "Also OMLX_TTS_MODEL env."
    )
    parser.add_argument(
        "--voice-desc", type=str,
        default="A deep, measured, authoritative American male voice. Military precision. Deliberate pauses.",
        help="Voice description for Qwen3-TTS Voice Design (TARS default voice)"
    )
    parser.add_argument("--speed", type=float, default=1.0, help="TTS speed (default: 1.0)")

    # Output
    parser.add_argument("--no-voice", action="store_true", help="Text-only mode, no audio")
    parser.add_argument("--no-save", action="store_true", help="Don't save audio files")

    return parser.parse_args()


# ── Boot Sequence ────────────────────────────────────────────────────────

def print_boot_sequence(config: TARSConfig):
    """TARS-style boot animation."""

    boot_text = """
 ╔══════════════════════════════════════════════════════════╗
 ║                                                          ║
 ║   ████████╗ █████╗ ██████╗ ███████╗     █████╗ ██╗       ║
 ║   ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝    ██╔══██╗██║       ║
 ║      ██║   ███████║██████╔╝███████╗    ███████║██║       ║
 ║      ██║   ██╔══██║██╔══██╗╚════██║    ██╔══██║██║       ║
 ║      ██║   ██║  ██║██║  ██║███████║    ██║  ██║██║       ║
 ║      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝       ║
 ║                                                          ║
 ║   Tactical Autonomous Robotic System                     ║
 ║   USMC Serial: TARS-001  |  MLX Native                   ║
 ║                                                          ║
 ╚══════════════════════════════════════════════════════════╝"""

    console.print(boot_text, style="bold cyan")

    # Simulated boot log
    boot_steps = [
        ("Initializing neural matrix", 0.3),
        ("Loading personality parameters", 0.2),
        (f"  Humor: {config.personality.humor}%", 0.1),
        (f"  Honesty: {config.personality.honesty}%", 0.1),
        (f"  Discretion: {config.personality.discretion}%", 0.1),
        (f"  Trust: {config.personality.trust}%", 0.1),
        (f"LLM: {config.omlx.model} via OMLX @ {config.omlx.server_url}", 0.2),
        (f"TTS: {config.tts.model} (Voice Design) via OMLX @ {config.tts.speed}x", 0.2),
        ("Runtime: OMLX server (LLM + TTS)", 0.2),
        ("Articulation servos: online", 0.2),
        ("Crew manifest: Brand, Dr. Mann, Prof. Brand, Murphy — standing by", 0.2),
        ("All systems nominal", 0.3),
    ]

    for step, delay in boot_steps:
        time.sleep(delay)
        if step.startswith("  "):
            console.print(f"  [dim]{step}[/dim]")
        else:
            console.print(f"  [green]>[/green] {step}")

    console.print()
    p = config.personality
    console.print(
        Panel(
            f"[bold]TARS online.[/bold] {p.summary()}\n\n"
            f"[dim]Commands: 'quit' to exit | 'reset' to clear history | "
            f"'set humor to N' to adjust personality | 'settings' to view\n"
            f"'save [name]' to save session | 'load <name>' to restore | "
            f"'history' to list saved sessions\n"
            f"'call <name>' to summon crew | 'dismiss <name>' to send away | "
            f"'who\\'s here?' to check roster\n"
            f"Crew: Brand, Dr. Mann, Prof. Brand, Murphy[/dim]",
            border_style="cyan",
        )
    )
    console.print()


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
    )

    tts_config = TTSConfig(
        model=args.tts_model,
        voice_desc=args.voice_desc,
        speed=args.speed,
    )

    config = TARSConfig(
        personality=personality,
        omlx=omlx_config,
        tts=tts_config,
        play_audio=not args.no_voice,
        save_audio=not args.no_save,
    )

    # Validate
    try:
        config.validate()
    except (ValueError, EnvironmentError) as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        sys.exit(1)

    # Boot
    print_boot_sequence(config)

    # Initialize LLM (OMLX client — the connection is lazy; the model loads on
    # the first chat, so that request can be slow after a cold start).
    console.print(f"  [yellow]Connecting to OMLX server at {config.omlx.server_url}...[/yellow]")
    try:
        agent = TARSAgent(config)
        console.print("  [green]>[/green] OMLX client ready")
        console.print(
            f"  [dim]Model '{config.omlx.model}' loads on demand — first reply may be slow.[/dim]\n"
        )
    except Exception as e:
        console.print(f"[red]LLM init failed:[/red] {e}")
        console.print(f"[dim]Ensure OMLX is running and serving '{config.omlx.model}'.[/dim]")
        console.print(f"[dim]Dashboard: {config.omlx.dashboard_url}[/dim]")
        sys.exit(1)

    # Initialize TTS (OMLX audio client — synthesis happens on the OMLX server)
    voice: TARSVoice | None = None
    if not args.no_voice:
        try:
            voice = TARSVoice(config)
        except Exception as e:
            console.print(f"[yellow]Voice init failed: {e}[/yellow]")
            console.print("[yellow]Falling back to text-only mode.[/yellow]")
            voice = None

    # Conversation loop
    while True:
        try:
            user_input = console.input("[bold white]Cooper>[/bold white] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cyan]TARS:[/cyan] See you on the other side, Cooper.")
            if voice:
                voice.wait()
            agent._save_conversation("autosave")
            break

        if not user_input:
            continue

        # Meta commands
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[cyan]TARS:[/cyan] Don't let me leave, Murph.")
            if voice:
                voice.wait()
            agent._save_conversation("autosave")
            break

        if user_input.lower() == "reset":
            agent.reset()
            console.print("[cyan]TARS:[/cyan] Memory cleared. Starting fresh.")
            continue

        if user_input.lower() == "cleanup":
            if voice:
                voice.cleanup()
            console.print("[cyan]TARS:[/cyan] Audio files purged.")
            continue

        # Check for registered commands (settings, persistence, character management)
        cmd_response = agent.registry.dispatch(
            user_input, agent.config, agent._command_context()
        )
        if cmd_response:
            console.print(f"[bold cyan]TARS:[/bold cyan] {cmd_response}")
            console.print()
            continue

        # Multi-character generation round
        try:
            responses = agent.orchestrator.generate_round(
                user_input,
                on_character_start=lambda char: console.print(
                    f"[{char.color_style}]{char.display_name}:[/{char.color_style}] ",
                    end="",
                ),
                on_character_token=lambda cid, tok: console.print(
                    tok, end="", highlight=False
                ),
                on_character_end=lambda char, text: _handle_character_end(
                    char, text, agent, voice, config
                ),
            )

            # If all characters were silent (shouldn't happen since TARS never is)
            if all(r.silent for r in responses):
                console.print("[dim]...[/dim]")

        except Exception as e:
            console.print()
            console.print(f"[red]Error:[/red] {e}")
            continue

        console.print()


def _handle_character_end(
    char,
    text: str,
    agent: TARSAgent,
    voice: TARSVoice | None,
    config: TARSConfig,
):
    """Handle end of a character's response: newline, TPS, TTS."""
    console.print()  # newline after streaming

    # Show tokens/sec
    tps = agent.llm.last_generation_tps
    if tps > 0:
        console.print(f"  [dim]{tps:.1f} tokens/sec[/dim]")

    # Speak with character's voice
    if voice:
        try:
            audio_path = voice.speak(text, voice_desc=char.voice_desc, speed=char.speed)
            if audio_path and config.save_audio:
                console.print(f"  [dim]Audio: {audio_path}[/dim]")
        except Exception as e:
            console.print(f"  [dim yellow]Voice error: {e}[/dim yellow]")


if __name__ == "__main__":
    main()
