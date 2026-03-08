"""CLI entry point and main async loop for the push-to-talk voice interface."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import re
import sys

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from .audio_utils import is_silent, is_too_short, trim_silence
from .config import Config
from .display import Display
from .hotkey import HotkeyListener
from .recorder import AudioRecorder
from .session import ClaudeSession
from .transcriber import Transcriber

# ── Mode switching via voice ────────────────────────────────────────

# Maps friendly voice phrases to SDK permission modes.
_MODE_ALIASES: dict[str, str] = {
    "plan": "plan",
    "plan mode": "plan",
    "planning mode": "plan",
    "normal": "default",
    "normal mode": "default",
    "default mode": "default",
    "auto edit": "acceptEdits",
    "auto edits": "acceptEdits",
    "accept edits": "acceptEdits",
    "accept edits mode": "acceptEdits",
}

# Friendly display names for each SDK permission mode.
_MODE_LABELS: dict[str, str] = {
    "default": "Normal",
    "plan": "Plan",
    "acceptEdits": "Auto-edit",
}

# Build a regex that matches "switch to <mode>" / "enter <mode>" / just "<mode>" at
# the start of the utterance (case-insensitive).  Sorted longest-first so
# "planning mode" matches before "plan".
_sorted_aliases = sorted(_MODE_ALIASES.keys(), key=len, reverse=True)
_alias_pattern = "|".join(re.escape(a) for a in _sorted_aliases)
_MODE_RE = re.compile(
    rf"^(?:switch\s+to|enter|go\s+to|use|activate|enable)?\s*(?:the\s+)?({_alias_pattern})\s*$",
    re.IGNORECASE,
)


def _parse_mode_command(text: str) -> str | None:
    """If *text* is a mode-switch command, return the SDK permission mode name."""
    m = _MODE_RE.match(text.strip())
    if m:
        return _MODE_ALIASES[m.group(1).lower()]
    return None


async def main_loop(config: Config) -> None:
    display = Display(
        max_width=config.max_response_width,
        abort_presses=config.abort_presses,
    )

    # --- Preflight checks ---
    if not AudioRecorder.check_microphone():
        display.error("No microphone found. Connect a mic and try again.")
        sys.exit(1)

    display.info("Loading whisper model (first run downloads ~1.5 GB)...")
    try:
        transcriber = Transcriber(model=config.whisper_model)
    except RuntimeError as e:
        display.error(str(e))
        sys.exit(1)

    recorder = AudioRecorder(sample_rate=config.sample_rate, channels=config.channels)
    hotkey = HotkeyListener(hotkey=config.hotkey)
    session = ClaudeSession(cwd=config.cwd, permission_mode=config.permission_mode)

    loop = asyncio.get_running_loop()
    hotkey.start(loop)

    display.info(f"Hotkey: {config.hotkey}")
    display.info(f"Working directory: {config.cwd}")
    display.mode_badge(session.permission_mode)
    display.separator()

    try:
        await session.start()
        display.ready()

        while True:
            # 1. Wait for key press
            hotkey.reset()
            await hotkey.pressed.wait()

            # 2. Start recording
            display.recording()
            recorder.start()

            # 3. Wait for key release
            await hotkey.released.wait()

            # 4. Stop recording
            audio = recorder.stop()

            # 5. Validate audio
            if is_too_short(audio, config.sample_rate, config.min_duration):
                display.info("Too short — ignored")
                display.ready()
                continue

            audio = trim_silence(audio, threshold=config.silence_threshold_rms)

            if audio.size == 0 or is_silent(audio, config.silence_threshold_rms):
                display.no_speech()
                display.ready()
                continue

            # 6. Transcribe
            display.transcribing()
            text = await transcriber.transcribe(audio)

            if not text or text.isspace():
                display.no_speech()
                display.ready()
                continue

            display.user_text(text)

            # 6b. Check for mode-switch commands
            new_mode = _parse_mode_command(text)
            if new_mode is not None:
                await session.set_permission_mode(new_mode)
                display.mode_badge(new_mode)
                display.separator()
                display.ready()
                continue

            # 7. Send to Claude and stream response (with abort support)
            await _stream_with_abort(
                session, display, hotkey, text,
                abort_presses=config.abort_presses,
                abort_window=config.abort_window,
            )

            display.separator()
            display.ready()

    except KeyboardInterrupt:
        display.info("Shutting down...")
    finally:
        hotkey.stop()
        await session.stop()


async def _wait_for_abort(
    hotkey: HotkeyListener,
    display: Display,
    required: int,
    window: float,
) -> None:
    """Wait for *required* hotkey taps within *window* seconds.

    Each tap updates the spinner with progress (e.g. "aborting: 2/3").
    If the user pauses too long between taps, old ones expire and the
    counter effectively resets.
    """
    timestamps: list[float] = []
    loop = asyncio.get_event_loop()

    while True:
        hotkey.pressed.clear()
        await hotkey.pressed.wait()

        now = loop.time()
        timestamps.append(now)
        # Only keep taps within the rolling window
        timestamps = [t for t in timestamps if now - t <= window]

        display.show_abort_progress(len(timestamps))

        if len(timestamps) >= required:
            return  # abort triggered

        # Wait for the key to be released so the next physical tap registers
        hotkey.released.clear()
        await hotkey.released.wait()


async def _stream_with_abort(
    session: ClaudeSession,
    display: Display,
    hotkey: HotkeyListener,
    text: str,
    *,
    abort_presses: int = 3,
    abort_window: float = 2.0,
) -> None:
    """Stream Claude's response while monitoring the hotkey for abort.

    Races two tasks:
      - ``_stream``: iterates over the SDK response, collecting text and actions
      - ``_wait_for_abort``: counts hotkey taps (default 3 within 2 s)

    If the user taps enough times, the stream is cancelled, an interrupt
    is sent to the SDK, and partial results are shown.
    """
    full_text_parts: list[str] = []

    async def _stream() -> None:
        async for message in session.send(text):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        full_text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        preview = str(block.input)[:200] if block.input else ""
                        display.record_action(block.name, preview)

    display.start_streaming()

    # Clear events so we detect only *new* taps during streaming.
    hotkey.pressed.clear()
    hotkey.released.clear()

    stream_task = asyncio.create_task(_stream())
    abort_task = asyncio.create_task(
        _wait_for_abort(hotkey, display, abort_presses, abort_window)
    )

    try:
        done, pending = await asyncio.wait(
            {stream_task, abort_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel whichever task is still running
        for task in pending:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        if abort_task in done:
            # ── User aborted ────────────────────────────────────────
            display.stop_streaming(aborted=True)
            display.abort_notice()

            # Tell the SDK to stop generating
            with contextlib.suppress(Exception):
                await session.interrupt()

            # Show whatever partial text we collected
            if full_text_parts:
                display.assistant_text("".join(full_text_parts))

            # Wait for the key to be released so the next cycle starts clean
            if hotkey.is_held:
                await hotkey.released.wait()
        else:
            # ── Normal completion ───────────────────────────────────
            # Re-raise any exception from the stream
            stream_task.result()

            display.stop_streaming(aborted=False)
            if full_text_parts:
                display.assistant_text("".join(full_text_parts))

    except Exception as e:
        display.stop_streaming(aborted=True)
        display.error(f"Claude Code error: {e}")
        display.info("Resetting session...")
        await session.stop()
        await session.start()


def cli() -> None:
    """Parse CLI arguments and run the main loop."""
    parser = argparse.ArgumentParser(
        prog="taulk",
        description="Push-to-talk voice interface for Claude Code",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory for Claude Code (default: current directory)",
    )
    parser.add_argument(
        "--hotkey",
        default="Key.alt_r",
        help="Hotkey for push-to-talk (default: Key.alt_r — right option key)",
    )
    parser.add_argument(
        "--model",
        default="mlx-community/whisper-large-v3-turbo",
        help="Whisper model to use (default: mlx-community/whisper-large-v3-turbo)",
    )
    parser.add_argument(
        "--permission-mode",
        default="default",
        choices=["default", "plan", "acceptEdits"],
        help="Claude Code permission mode (default: default)",
    )

    args = parser.parse_args()

    config = Config(
        hotkey=args.hotkey,
        whisper_model=args.model,
        permission_mode=args.permission_mode,
    )
    if args.cwd is not None:
        config.cwd = args.cwd

    try:
        asyncio.run(main_loop(config))
    except KeyboardInterrupt:
        # The inner main_loop already prints "Shutting down..." and cleans up.
        # This outer catch ensures no ugly traceback if the interrupt escapes
        # asyncio teardown.
        pass

    print("\n  Goodbye!\n")


if __name__ == "__main__":
    cli()
