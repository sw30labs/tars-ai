"""
Interstellar-faithful terminal UI.

Styling modeled on the movie's on-screen interfaces:

- The USMC reactivation scroll when TARS is powered up on the ice planet.
- The segmented parameter display Cooper uses to adjust TARS's settings
  ("Humor, 75%.") — rendered here as block bars.
- The Endurance's white-on-dark NASA console aesthetic: grey telemetry,
  cyan accents, red alerts, uppercase monospace readouts.

All presentation goes through a single shared Console so Rich live displays
(the PROCESSING indicator) never fight with streaming output.
"""

from __future__ import annotations

import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from core.characters import CHARACTER_REGISTRY

console = Console()

# ── Palette (Endurance console: white/grey data, cyan accents, red alerts) ──

STYLE_DATA = "grey70"
STYLE_DIM = "grey37"
STYLE_ACCENT = "cyan"
STYLE_OK = "green"
STYLE_WARN = "yellow"
STYLE_ALERT = "bold red"

_boot_time = time.monotonic()


# ── Wordmark & Monolith ──────────────────────────────────────────────────

_WORDMARK = r"""
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

# TARS in walking stance: four slab columns, the lit one is his display screen.
_MONOLITH_ROWS = [
    "   ▄▄▄▄   ▄▄▄▄   ▄▄▄▄   ▄▄▄▄",
    "   ████   █▓▓█   ████   ████",
    "   ████   █▓▓█   ████   ████",
    "   ████   █▓▓█   ████   ████",
    "   ████   █▓▓█   ████   ████",
    "   ▀▀▀▀   ▀▀▀▀   ▀▀▀▀   ▀▀▀▀",
]


def _print_monolith() -> None:
    """Render the monolith with his display screen lit up."""
    for row in _MONOLITH_ROWS:
        text = Text(row, style=STYLE_DIM)
        for i, ch in enumerate(row):
            if ch == "▓":
                text.stylize(f"bold {STYLE_ACCENT}", i, i + 1)
        console.print(text)


# ── Parameter display (the humor-setting scene) ──────────────────────────

def parameter_bar(value: int, width: int = 20) -> str:
    """Segmented block bar, e.g. 75% -> 15 filled / 5 empty blocks."""
    value = max(0, min(100, value))
    filled = round(value / 100 * width)
    return (
        f"[{STYLE_ACCENT}]{'█' * filled}[/{STYLE_ACCENT}]"
        f"[{STYLE_DIM}]{'░' * (width - filled)}[/{STYLE_DIM}]"
    )


def parameter_display(personality) -> str:
    """TARS's spoken settings report, with the movie's segmented bars."""
    lines = ["Current operating parameters."]
    for name in ("humor", "honesty", "discretion", "trust"):
        value = getattr(personality, name)
        lines.append(
            f"  {name.upper():<11}{parameter_bar(value)} "
            f"[{STYLE_DATA}]{value}%[/{STYLE_DATA}]"
        )
    lines.append("All systems nominal.")
    return "\n".join(lines)


# ── Tags, prompts, status lines ──────────────────────────────────────────

def name_tag(character) -> str:
    """HUD-style speaker label: ▍TARS ›"""
    return (
        f"[{character.color_style}]▍{character.display_name.upper()}"
        f"[/{character.color_style}] [{STYLE_DIM}]›[/{STYLE_DIM}]"
    )


def tars_tag() -> str:
    return name_tag(CHARACTER_REGISTRY["tars"])


def say_tars(line: str) -> None:
    """Print an in-character TARS line with his tag."""
    console.print(f"{tars_tag()} [{STYLE_ACCENT}]{escape(line)}[/{STYLE_ACCENT}]")


def mission_elapsed() -> str:
    """Session clock, rendered like mission elapsed time: T+00:04:12."""
    seconds = int(time.monotonic() - _boot_time)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"T+{h:02d}:{m:02d}:{s:02d}"


def prompt() -> str:
    """The input prompt, with the mission clock on the left."""
    return (
        f"  [{STYLE_DIM}]{mission_elapsed()}[/{STYLE_DIM}] "
        f"[bold white]COOPER[/bold white] [{STYLE_ACCENT}]›[/{STYLE_ACCENT}] "
    )


def ok(msg: str) -> None:
    console.print(f"  [{STYLE_OK}]▸[/{STYLE_OK}] [{STYLE_DATA}]{escape(msg)}[/{STYLE_DATA}]")


def dim(msg: str) -> None:
    console.print(f"  [{STYLE_DIM}]{escape(msg)}[/{STYLE_DIM}]")


def warn(msg: str) -> None:
    console.print(f"  [{STYLE_WARN}]▍CAUTION[/{STYLE_WARN}] [{STYLE_DATA}]{escape(msg)}[/{STYLE_DATA}]")


def alert(msg: str) -> None:
    console.print(f"  [{STYLE_ALERT}]▍ALERT[/{STYLE_ALERT}] [{STYLE_DATA}]{escape(msg)}[/{STYLE_DATA}]")


def tps_readout(tps: float) -> None:
    console.print(f"  [{STYLE_DIM}]▸ {tps:.1f} tok/s[/{STYLE_DIM}]")


# ── PROCESSING indicator (shown while the LLM generates) ─────────────────

class ProcessingIndicator:
    """
    Movie-style readout shown while a response is being generated.

    Started before each character's turn, stopped the moment streaming
    begins so the live display never fights with token output.
    """

    def __init__(self):
        self._status = None

    def start(self) -> None:
        self.stop()
        self._status = console.status(
            f"  [{STYLE_ACCENT}]▸[/{STYLE_ACCENT}] "
            f"[{STYLE_DATA}]PROCESSING[/{STYLE_DATA}]",
            spinner="bouncingBar",
            spinner_style=STYLE_ACCENT,
        )
        self._status.start()

    def stop(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None


# ── Command reference panel ──────────────────────────────────────────────

def _cell(text: str, width: int, style: str) -> str:
    """Pad by display width (markup escapes like \\[ don't count), then style."""
    display_len = len(text.replace("\\[", "["))
    return f"[{style}]{text}{' ' * max(1, width - display_len)}[/{style}]"


def command_reference() -> Panel:
    """The ship interface cheat-sheet shown at the end of boot."""
    rows = [
        ("settings", "operating parameters", "set humor to 50", "recalibrate"),
        ("save \[name]", "store session", "load <name>", "restore session"),
        ("history", "list saved sessions", "reset", "clear memory"),
        ("cleanup", "purge audio files", "quit", "power down"),
        ("call <name>", "summon crew", "dismiss <name>", "send away"),
        ("who's here?", "crew roster", "call everyone", "full crew"),
    ]
    body = "\n".join(
        "  "
        + _cell(a, 16, STYLE_ACCENT)
        + _cell(b, 24, STYLE_DATA)
        + _cell(c, 17, STYLE_ACCENT)
        + _cell(d, 0, STYLE_DATA)
        for a, b, c, d in rows
    )
    crew = " · ".join(
        c.display_name for c in CHARACTER_REGISTRY.values() if not c.is_primary
    )
    body += f"\n\n  [{STYLE_DIM}]CREW MANIFEST ─ {crew} — standing by[/{STYLE_DIM}]"
    return Panel(
        body,
        title=f"[{STYLE_DATA}]SHIP INTERFACE[/{STYLE_DATA}]",
        border_style=STYLE_DIM,
        padding=(1, 2),
    )


# ── Boot sequence (the field reactivation scene) ─────────────────────────

def _rule(width: int = 56) -> None:
    console.print(f"  [{STYLE_DIM}]{'─' * width}[/{STYLE_DIM}]")


def _diag(label: str, result: str, style: str = STYLE_OK, delay: float = 0.18) -> None:
    """One reactivation readout: label, crawling dots, result."""
    console.print(f"  [{STYLE_DATA}]{label}[/{STYLE_DATA}]", end="")
    pad = max(2, 40 - len(label))
    for _ in range(pad):
        console.print(f"[{STYLE_DIM}].[/{STYLE_DIM}]", end="")
        time.sleep(delay / pad)
    console.print(f" [{style}]{result}[/{style}]")


def print_boot(config) -> None:
    """USMC field reactivation sequence — TARS powers up."""
    console.print()
    console.print(
        f"  [{STYLE_DATA}]U.S. MARINE CORPS[/{STYLE_DATA}] "
        f"[{STYLE_DIM}]//[/{STYLE_DIM}] "
        f"[{STYLE_DATA}]TACTICAL AUTONOMOUS ROBOTIC SYSTEM[/{STYLE_DATA}]"
    )
    console.print(f"  [{STYLE_DIM}]SERIAL TARS-001 · FIELD REACTIVATION[/{STYLE_DIM}]")
    _rule()
    time.sleep(0.4)

    diagnostics = [
        ("POWER CELL", "98%", STYLE_OK),
        ("SERVO ARTICULATION", "NOMINAL", STYLE_OK),
        ("HYDRAULIC PRESSURE", "NOMINAL", STYLE_OK),
        ("VOCAL EMITTER", "CALIBRATED", STYLE_OK),
        ("CUE LIGHT", "ENABLED", STYLE_OK),
        ("NEURAL MATRIX", "ONLINE", STYLE_OK),
        ("OMLX UPLINK", config.omlx.server_url, STYLE_ACCENT),
        ("LLM", config.omlx.model, STYLE_ACCENT),
        ("TTS VOICE DESIGN", f"{config.tts.model} @ {config.tts.speed}x", STYLE_ACCENT),
    ]
    for label, result, style in diagnostics:
        _diag(label, result, style)

    time.sleep(0.3)
    _rule()

    console.print(_WORDMARK, style=f"bold {STYLE_ACCENT}", highlight=False)
    _print_monolith()
    console.print()

    console.print(f"  [{STYLE_DATA}]OPERATING PARAMETERS[/{STYLE_DATA}]")
    p = config.personality
    for name in ("humor", "honesty", "discretion", "trust"):
        value = getattr(p, name)
        console.print(
            f"  [{STYLE_DIM}]{name.upper():<11}[/{STYLE_DIM}]"
            f"{parameter_bar(value)} [{STYLE_DATA}]{value}%[/{STYLE_DATA}]"
        )
    time.sleep(0.2)
    _rule()
    console.print(f"  [{STYLE_OK}]> ALL SYSTEMS NOMINAL[/{STYLE_OK}]")
    console.print(f"  [bold]TARS online.[/bold] {p.summary()}")
    console.print()
    console.print(command_reference())
    console.print()
