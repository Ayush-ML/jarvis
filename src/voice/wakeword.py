# This Script is responsible for Wake-word detection using OpenWakeWord's built-in hey_jarvis model
# Loads the model once and exposes check() per audio chunk -- same reasoning as Transcriber/VAD:
# the model needs to persist across calls rather than reload every time, which is why this is a
# class and not a bare function. Supersedes the previous standalone wakeword() function, which
# owned its own PyAudio stream and loop internally -- that design couldn't compose with VAD/AEC
# needing to run on the SAME stream, which VoiceListener (src/voice/listener.py) now needs to do.
import numpy as np
import openwakeword
from typing import Iterable
from src.core.config import THRESHOLD

DEFAULT_MODELS = ("hey_jarvis",)


class WakeWordDetector:
    """
    Construct ONCE per audio stream/thread -- same lifecycle and thread-safety
    caveat as Transcriber/VoiceActivityDetector.
    """

    def __init__(self, threshold: float = THRESHOLD, wakeword_models: Iterable[str] = DEFAULT_MODELS) -> None:
        self._model = openwakeword.model.Model(
            wakeword_models=list(wakeword_models),
            inference_framework="onnx",
        )
        self._threshold = threshold

    def check(self, pcm: np.ndarray) -> bool:
        """
        Feed one audio chunk -- this project uses CHUNK=1280 samples (80ms at
        16kHz), the same input format the original wakeword() implementation
        used, so no new assumption is introduced here. Returns True at most
        once per trigger and resets the model's internal state when it does.
        """
        predictions = self._model.predict(pcm)
        for _, score in predictions.items():
            if score >= self._threshold:
                self._model.reset()
                return True
        return False

    def reset(self) -> None:
        self._model.reset()
