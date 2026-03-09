# CLAUDE.md

## Project overview

**Taulk** — a push-to-talk voice interface for Claude Code. Hold a hotkey, speak, release, and Claude Code executes the request. All transcription runs locally via MLX Whisper on Apple Silicon.

## Tech stack

- Python 3.10+, async (`anyio`/`asyncio`)
- `claude-agent-sdk` for Claude Code integration
- `mlx-whisper` for on-device speech-to-text
- `pynput` for global hotkey listening
- `sounddevice` + `soundfile` for audio capture
- `rich` for terminal UI
- Build: `hatchling` / `uv`

## Project structure

```
src/command/
├── main.py          # CLI entry point and async event loop
├── session.py       # Claude Code SDK session management
├── hotkey.py        # Global hotkey listener (pynput → asyncio bridge)
├── recorder.py      # Audio recording via sounddevice
├── transcriber.py   # Speech-to-text via MLX Whisper
├── config.py        # Configuration defaults
├── display.py       # Terminal UI (Rich)
└── audio_utils.py   # Audio validation helpers
```

## Key commands

```bash
# Install
pip install .    # or: uv pip install .

# Run
taulk
taulk --cwd ~/projects/my-app
taulk --hotkey Key.alt_l
taulk --model mlx-community/whisper-small
```

## Design principles

- **Local-only audio** — no audio leaves the machine; MLX Whisper runs on-device.
- **Path sandboxing** — Claude Code file operations are restricted to the configured working directory.
- **Async everywhere** — recording, transcription, streaming, and abort detection run concurrently.
- **Audio validation** — short accidental taps (< 300 ms) and silence are filtered before transcription.

## Conventions

- Entry point: `command.main:cli` (registered as `taulk` script)
- Package lives under `src/command/`
- Use `uv` for dependency management (lockfile: `uv.lock`)
