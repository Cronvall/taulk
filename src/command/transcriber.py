"""Local speech-to-text using mlx-whisper on Apple Silicon."""

from __future__ import annotations

import platform

import anyio
import numpy as np


class Transcriber:
    """Wraps mlx-whisper for async transcription."""

    def __init__(self, model: str = "mlx-community/whisper-large-v3-turbo") -> None:
        if platform.machine() != "arm64":
            raise RuntimeError(
                "mlx-whisper requires Apple Silicon (arm64). "
                f"Detected: {platform.machine()}"
            )
        self.model = model
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Import mlx_whisper (triggers model download on first use)."""
        if not self._loaded:
            import mlx_whisper  # noqa: F401

            self._loaded = True

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        """Run transcription synchronously (called in a thread)."""
        import mlx_whisper

        self._ensure_loaded()
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.model,
            language="en",
        )
        text: str = result.get("text", "").strip()
        return text

    async def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio array to text. Runs in a worker thread."""
        text = await anyio.to_thread.run_sync(self._transcribe_sync, audio)
        return text
