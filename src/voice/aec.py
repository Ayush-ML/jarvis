# This Script is responsible for Acoustic Echo Cancellation (AEC) using WebRTC's AEC3 algorithm,
# via pywebrtc-audio (pybind11 bindings over the actual Chrome/WebRTC audio processing module --
# prebuilt wheels for Windows/Linux/macOS, no compile toolchain needed on this machine).
#
# ============================================================================================
# THIS CLASS ALONE DOES NOT CANCEL ANY ECHO YET -- IT NEEDS A REFERENCE SIGNAL THAT DOES NOT
# EXIST IN THIS CODEBASE. process(near, far) requires `far`: the EXACT audio samples currently
# being sent to the speaker, sample-count-aligned with `near` (the mic capture) and roughly
# time-aligned (AEC3's internal delay estimator handles the rest, helped by
# config.AEC_STREAM_DELAY_MS as a convergence hint).
#
# Right now, src/voice/tts.py pipes Edge TTS's compressed audio bytes straight into an external
# `ffplay` subprocess's stdin. Nothing in this Python process ever sees the decoded PCM that
# actually reaches the speaker -- there is currently NO source for `far`. Making this class do
# anything real requires:
#   1. Rewriting tts.py to decode and own playback itself (e.g. write PCM to a PyAudio output
#      stream) instead of handing off to ffplay, so the exact played samples can also be queued
#      as the reference signal.
#   2. Reconciling Edge TTS's actual output sample rate against this pipeline's 16kHz.
#   3. A synchronization mechanism so that for every `near` chunk captured, the matching `far`
#      chunk (what was playing at that same moment) is available -- two independently-buffered
#      OS audio streams, so this is a real timing problem, not just "grab the last N samples."
# None of that is implemented here. This file is only the verified, ready-to-use cancellation
# primitive -- correct now, inert until the plumbing above exists.
# ============================================================================================
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
        far:  the reference signal for what's playing on the speaker RIGHT NOW,
              same length and dtype as `near`. There is no source for this in
              this codebase yet (see module docstring) -- passing silence,
              stale audio, or misaligned audio here doesn't raise an error,
              it just produces bad or no cancellation. Correctness of `far`
              is entirely the caller's responsibility; this method cannot
              detect or warn about a wrong reference signal.
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
