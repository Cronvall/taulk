"""Audio recording using sounddevice."""

import queue

import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Records audio from the default input device at 16kHz mono float32."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: sd.InputStream | None = None

    def _callback(self, indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        """PortAudio callback — runs on audio thread, only enqueues data."""
        if status:
            pass  # Drop-outs are non-fatal
        self._queue.put_nowait(indata.copy())

    def start(self) -> None:
        """Start recording."""
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        """Stop recording and return the captured audio as a 1-D float32 array."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        chunks: list[np.ndarray] = []
        while not self._queue.empty():
            chunks.append(self._queue.get_nowait())

        if not chunks:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(chunks, axis=0)
        # Flatten to 1-D (mono)
        if audio.ndim > 1:
            audio = audio[:, 0]
        return audio

    @staticmethod
    def check_microphone() -> bool:
        """Return True if a default input device is available."""
        try:
            sd.query_devices(kind="input")
            return True
        except sd.PortAudioError:
            return False
