"""Audio utility functions: silence trimming, duration checks, RMS."""

import numpy as np


def compute_rms(audio: np.ndarray) -> float:
    """Compute root mean square of audio signal."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio**2)))


def is_too_short(audio: np.ndarray, sample_rate: int, min_duration: float) -> bool:
    """Check if audio is shorter than minimum duration."""
    duration = len(audio) / sample_rate
    return duration < min_duration


def is_silent(audio: np.ndarray, threshold: float) -> bool:
    """Check if audio is effectively silent."""
    return compute_rms(audio) < threshold


def trim_silence(audio: np.ndarray, threshold: float = 0.01, frame_length: int = 1024) -> np.ndarray:
    """Trim leading and trailing silence from audio."""
    if audio.size == 0:
        return audio

    # Compute RMS per frame
    n_frames = len(audio) // frame_length
    if n_frames == 0:
        return audio

    frames = audio[: n_frames * frame_length].reshape(n_frames, frame_length)
    rms = np.sqrt(np.mean(frames**2, axis=1))

    # Find first and last non-silent frames
    non_silent = np.where(rms > threshold)[0]
    if len(non_silent) == 0:
        return np.array([], dtype=audio.dtype)

    start = non_silent[0] * frame_length
    end = min((non_silent[-1] + 1) * frame_length, len(audio))
    return audio[start:end]
