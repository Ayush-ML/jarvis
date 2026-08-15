# This Script is responsible for Voice Activity Detection using Silero VAD (ONNX backend)
# Wraps Silero's own VADIterator, which already implements the actual threshold / min-silence
# / edge-padding logic -- this class's real job is reconciling the FIXED 512-sample-at-16kHz
# window Silero requires against whatever chunk size the caller's audio stream actually
# delivers (this project's CHUNK is 1280 samples, which doesn't divide evenly into 512 --
# 1280 / 512 = 2.5 -- so leftover samples have to carry over between calls).
#
# IMPORTANT -- VAD_SPEECH_PAD_MS does NOT give you back audio. VADIterator's 'start' event
# reports a sample index earlier than "now" (shifted back by speech_pad_ms), but it only
# reports the INDEX, not the audio itself -- nothing in Silero or this class retains PCM
# from before an event fires. If a caller (the future wakeword.py command-capture loop)
# wants that pre-roll audio for real, IT needs its own short rolling buffer of raw PCM and
# must slice from `start_sample` itself once a 'start' event arrives.
#
# Runs fully local via onnxruntime -- no API key, no network call. Note: the `silero-vad`
# pip package imports torch/torchaudio unconditionally even on the ONNX inference path, so
# torch lands as an install dependency regardless -- inference itself stays ONNX-only and
# the model is ~2MB, so this doesn't cost meaningful runtime RAM, just a heavier pip install.
import numpy as np
import torch
from typing import Dict, List
from silero_vad import load_silero_vad, VADIterator
from src.core.config import SAMPLE_RATE, VAD_THRESHOLD, VAD_SILENCE_MS, VAD_SPEECH_PAD_MS

_WINDOW_SAMPLES_16K = 512  # Fixed by the Silero model itself -- not configurable
_WINDOW_SAMPLES_8K = 256


class VoiceActivityDetector:
    """
    Construct ONCE per audio stream/thread, same lifecycle as Transcriber --
    loading the model has real cost and internal state (the running sample
    buffer, VADIterator's own triggered/silence state) is stream-specific,
    so this is not safe to share across concurrent streams.

    Feed it audio chunks of ANY size via process(); it internally buffers
    and slices exact windows for Silero, and returns whichever speech
    start/end events fired while consuming that chunk (usually zero or
    one, but a large input chunk could span more than one).
    """

    def __init__(
        self,
        threshold: float = VAD_THRESHOLD,
        min_silence_ms: int = VAD_SILENCE_MS,
        speech_pad_ms: int = VAD_SPEECH_PAD_MS,
        sampling_rate: int = SAMPLE_RATE,
    ) -> None:
        if sampling_rate not in (8000, 16000):
            raise ValueError("Silero VAD only supports 8000 or 16000 Hz")
        model = load_silero_vad(onnx=True)
        self._iterator = VADIterator(
            model,
            threshold=threshold,
            sampling_rate=sampling_rate,
            min_silence_duration_ms=min_silence_ms,
            speech_pad_ms=speech_pad_ms,
        )
        self._window_samples = _WINDOW_SAMPLES_16K if sampling_rate == 16000 else _WINDOW_SAMPLES_8K
        self._buffer = np.empty(0, dtype=np.float32)

    def process(self, pcm: np.ndarray) -> List[Dict[str, int]]:
        """
        Feed in a chunk of int16 (or already-float32) mono PCM of any length.
        Returns a list of events fired while processing it -- each either
        {'start': sample_index} or {'end': sample_index}. sample_index is
        this detector's own running sample count since construction/reset(),
        not a byte offset into whatever the caller is doing with the audio --
        treat it as "how many samples back", not an absolute file position.
        """
        self._buffer = np.concatenate([self._buffer, self._to_float32(pcm)])
        events: List[Dict[str, int]] = []

        while len(self._buffer) >= self._window_samples:
            window = self._buffer[: self._window_samples]
            self._buffer = self._buffer[self._window_samples:]
            result = self._iterator(torch.from_numpy(window))
            if result is not None:
                events.append(result)

        return events

    def reset(self) -> None:
        """Clears VADIterator's internal state AND the leftover sample buffer. Call between separate listening sessions."""
        self._iterator.reset_states()
        self._buffer = np.empty(0, dtype=np.float32)

    @staticmethod
    def _to_float32(pcm: np.ndarray) -> np.ndarray:
        """Silero expects mono float32 samples in [-1, 1]; PyAudio/wakeword.py gives int16 -- same conversion as Transcriber._to_float32."""
        if pcm.dtype == np.int16:
            return pcm.astype(np.float32) / 32768.0
        return pcm.astype(np.float32)
