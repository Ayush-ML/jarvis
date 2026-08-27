# This Script is responsible for holding a short rolling buffer of the PCM Jarvis is CURRENTLY
# playing through the speaker, so AEC has a real reference ("far") signal to cancel against.
# tts.py pushes every chunk it plays; whatever pulls a mic chunk for AEC processing pulls the
# matching window from here via pull(). Thread-safe: the pusher (TTS's async playback loop)
# and the puller (a mic capture loop, expected on its own thread per wakeword.py's design)
# run on different threads.
#
# pull() is a non-destructive PEEK of the most recently played N samples, not a queue consume --
# this is a reasonable approximation, not a rigorously timestamped sync scheme. It relies on
# AEC3's own delay estimator (see aec.py / config.AEC_STREAM_DELAY_MS) to handle fine alignment,
# same as pywebrtc-audio's own docs describe. Expect this to need empirical tuning once real
# hardware round-trip latency can be measured, not a guaranteed-exact solution out of the box.
import threading
from collections import deque
import numpy as np
from src.core.config import SAMPLE_RATE

_MAX_BUFFER_SECONDS = 5  # Caps retained audio so a puller that stops pulling doesn't let this grow unbounded


class PlaybackReferenceBuffer:
    def __init__(self, sample_rate: int = SAMPLE_RATE, max_seconds: float = _MAX_BUFFER_SECONDS) -> None:
        self._max_samples = int(sample_rate * max_seconds)
        self._buffer: deque[np.ndarray] = deque()
        self._length = 0
        self._lock = threading.Lock()

    def push(self, pcm: np.ndarray) -> None:
        """Called by TTS playback with each chunk of int16 PCM as it's written to the speaker."""
        with self._lock:
            self._buffer.append(pcm)
            self._length += len(pcm)
            while self._length > self._max_samples and self._buffer:
                dropped = self._buffer.popleft()
                self._length -= len(dropped)

    def pull(self, num_samples: int) -> np.ndarray:
        """
        Returns exactly num_samples of int16 PCM: the most recently played audio, oldest-first.
        Zero-padded (silence) if less than num_samples has been played -- correct behavior when
        TTS isn't currently speaking, since silence means "no echo to cancel".
        """
        with self._lock:
            available = np.concatenate(list(self._buffer)) if self._buffer else np.empty(0, dtype=np.int16)

        if len(available) >= num_samples:
            return available[-num_samples:]

        pad = np.zeros(num_samples - len(available), dtype=np.int16)
        return np.concatenate([pad, available])

    def reset(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._length = 0


# Shared across TTS and every AEC consumer -- same reasoning as rate_limiter.default_rate_limiter:
# the pusher and puller are different call sites that both need to be talking about the same audio.
default_playback_reference = PlaybackReferenceBuffer()
