"""Configuration for the command voice interface."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Configuration with sensible defaults."""

    # Hotkey: right option/alt key by default
    hotkey: str = "Key.alt_r"

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    min_duration: float = 0.3  # seconds — ignore accidental taps
    silence_threshold_rms: float = 0.01

    # Whisper model
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"

    # Claude Code
    cwd: str = field(default_factory=lambda: str(Path.cwd()))
    permission_mode: str = "default"

    # Abort
    abort_presses: int = 3  # number of hotkey taps to abort
    abort_window: float = 2.0  # seconds — taps must happen within this window

    # Display
    max_response_width: int = 100
