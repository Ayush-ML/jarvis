# This Script is responsible for Speech-to-Text using faster-whisper
# Loading the model is the expensive part (a few seconds, ~1GB resident at "small"/int8) --
# that's the reason this is a class and not a bare function like tts()/wakeword(): the model
# needs to be loaded ONCE and reused across every transcription, not reloaded per call.
# Runs fully local and offline, no API key, no per-request cost.
import numpy as np
from typing import Union
from faster_whisper import WhisperModel
from src.core.config import STT_MODEL_SIZE, STT_DEVICE, STT_COMPUTE_TYPE, SAMPLE_RATE


class Transcriber:
    """
    Thin wrapper around a loaded WhisperModel. Construct ONCE at app startup
    (same lifecycle as Database/VectorStore) and reuse for every transcription --
    constructing this per-call would reload the model every time.
    """

    def __init__(
        self,
        model_size: str = STT_MODEL_SIZE,
        device: str = STT_DEVICE,
        compute_type: str = STT_COMPUTE_TYPE,
    ) -> None:
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_file(self, path: str) -> str:
        """Transcribes an audio file on disk (wav, mp3, etc. -- anything ffmpeg can decode)."""
        segments, _ = self.model.transcribe(path, beam_size=5)
        return self._join(segments)

    def transcribe_pcm(self, pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
        """
        Transcribes raw PCM samples directly -- no temp file needed. Accepts the exact
        format src/voice/wakeword.py already captures from PyAudio (int16 mono at
        SAMPLE_RATE), so a command buffer collected right after a wake-word trigger
        can be handed straight to this without any conversion on the caller's side.
        """
        if sample_rate != SAMPLE_RATE:
            raise ValueError(f"Expected {SAMPLE_RATE}Hz audio (config.SAMPLE_RATE), got {sample_rate}Hz")
        audio = self._to_float32(pcm)
        segments, _ = self.model.transcribe(audio, beam_size=5)
        return self._join(segments)

    @staticmethod
    def _to_float32(pcm: np.ndarray) -> np.ndarray:
        """faster-whisper expects mono float32 samples in [-1, 1]; PyAudio/wakeword.py gives int16."""
        if pcm.dtype == np.int16:
            return pcm.astype(np.float32) / 32768.0
        return pcm.astype(np.float32)

    @staticmethod
    def _join(segments) -> str:
        return " ".join(seg.text.strip() for seg in segments).strip()
