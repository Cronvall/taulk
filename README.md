# Taulk

Push-to-talk voice interface for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Hold a hotkey, speak, and let Claude Code do the rest — completely hands-free.

## How it works

1. **Hold** the hotkey (default: right Option key)
2. **Speak** your request
3. **Release** the key — your speech is transcribed locally and sent to Claude Code
4. **Watch** the response stream into your terminal

All speech processing happens on-device using [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper), so no audio ever leaves your machine.

## Requirements

- **macOS on Apple Silicon** (M1/M2/M3/M4) — required for MLX acceleration
- **Python 3.10+**
- **Claude Code** installed and authenticated
- A working **microphone**

## Installation

```bash
# Clone the repository
git clone https://github.com/oscarcronvall/command.git
cd command

# Install with pip (or uv)
pip install .
```

The first run will download the Whisper model (~1.5 GB).

## Usage

```bash
taulk
```

### CLI options

| Flag                 | Default                                    | Description                          |
| -------------------- | ------------------------------------------ | ------------------------------------ |
| `--cwd`              | Current directory                          | Working directory for Claude Code    |
| `--hotkey`           | `Key.alt_r` (right Option)                 | Push-to-talk key                     |
| `--model`            | `mlx-community/whisper-large-v3-turbo`     | Whisper model for transcription      |
| `--permission-mode`  | `default`                                  | `default`, `plan`, or `acceptEdits` |

### Examples

```bash
# Use a specific project directory
taulk --cwd ~/projects/my-app

# Use left Option key instead
taulk --hotkey Key.alt_l

# Use a smaller/faster Whisper model
taulk --model mlx-community/whisper-small
```

## Aborting a response

If Claude is generating a long response you don't need, **tap the hotkey 3 times within 2 seconds** to abort. Any partial output will still be displayed.

## Architecture

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

### Key design decisions

- **Local transcription** — MLX Whisper runs entirely on-device; no audio data is sent anywhere.
- **Path sandboxing** — A permission guard restricts Claude Code's file operations to the configured working directory, preventing accidental access outside your project.
- **Async event loop** — Recording, transcription, streaming, and abort detection all run concurrently via `asyncio`, keeping the interface responsive.
- **Audio validation** — Short accidental taps (< 300 ms) and silence are filtered out before transcription.

## License

MIT
