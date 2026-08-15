# This Script is responsible for Acoustic Echo Cancellation (AEC) using WebRTC's AEC3 algorithm,
# via pywebrtc-audio (pybind11 bindings, prebuilt Windows/Linux/macOS wheels). `far` -- the
# reference signal for what's currently playing on the speaker -- comes from
# src/voice/playback_reference.py, which tts.py now pushes into as it plays.
import numpy as np
from pywebrtc_audio import EchoCanceller as _WebRTCEchoCanceller
from src.core.config import SAMPLE_RATE, AEC_STREAM_DELAY_MS

_SUPPORTED_SAMPLE_RATES = (16000, 32000, 48000)


class EchoCanceller:
    """
    Construct ONCE per audio stream/thread -- same lifecycle and the same
    not-thread-safe caveat as Transcriber/VoiceActivityDetector. The
    underlying object holds adaptive-filter state specific to one ongoing
    mic/speaker pairing; sharing it across threads or streams will corrupt
    that state, not just risk a race.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        num_channels: int = 1,
        stream_delay_ms: int = AEC_STREAM_DELAY_MS,
    ) -> None:
        if sample_rate not in _SUPPORTED_SAMPLE_RATES:
            raise ValueError(f"pywebrtc-audio's EchoCanceller only supports {_SUPPORTED_SAMPLE_RATES} Hz")
        self._canceller = _WebRTCEchoCanceller(
            sample_rate=sample_rate,
            num_channels=num_channels,
            stream_delay_ms=stream_delay_ms,
        )

    def process(self, near: np.ndarray, far: np.ndarray) -> np.ndarray:
        """
        near: mic capture signal (int16 or float32, any length).
        far:  reference signal for what's playing on the speaker right now, same
              length and dtype as `near` -- pull this from PlaybackReferenceBuffer.pull(len(near)).
              Wrong/misaligned/stale `far` doesn't raise an error, it just produces
              bad or no cancellation -- correctness here is the caller's responsibility.
        Returns audio with echo removed -- same dtype and length as `near`.
        """
        if len(near) != len(far):
            raise ValueError(f"near ({len(near)} samples) and far ({len(far)} samples) must be the same length")
        return self._canceller.process(near, far)

    def reset(self) -> None:
        """Resets adaptive-filter state while keeping configuration. Call between separate listening sessions."""
        self._canceller.reset()

    @property
    def stream_delay_ms(self) -> int:
        return self._canceller.stream_delay_ms

    @stream_delay_ms.setter
    def stream_delay_ms(self, value: int) -> None:
        self._canceller.stream_delay_ms = value
