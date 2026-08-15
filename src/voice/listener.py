# This Script is responsible for the actual voice loop: wake detection -> command capture ->
# transcription, composing every primitive in this package (WakeWordDetector, EchoCanceller,
# VoiceActivityDetector, Transcriber, PlaybackReferenceBuffer) around ONE PyAudio input stream.
#
# CALLBACK CONTRACT: on_wake and on_command run SYNCHRONOUSLY on this loop's own thread. A slow
# handler (an LLM call, TTS playback) blocks stream.read() from being called during that time --
# PyAudio silently drops audio captured in that gap (exception_on_overflow=False, the same
# trade-off the original wakeword() already accepted). Dispatch slow work to another thread from
# inside your callback if you want the listener to keep listening while handling an event --
# this class does not do that for you.
import time
import threading
import numpy as np
import pyaudio
from enum import Enum, auto
from typing import Callable, List, Optional
from src.voice.wakeword import WakeWordDetector
from src.voice.vad import VoiceActivityDetector
from src.voice.aec import EchoCanceller
from src.voice.transcriber import Transcriber
from src.voice.playback_reference import default_playback_reference, PlaybackReferenceBuffer
from src.core.config import (
    SAMPLE_RATE, CHANNELS, CHUNK,
    COMMAND_START_TIMEOUT_SECONDS, VAD_MAX_COMMAND_SECONDS,
)


class _State(Enum):
    LISTENING = auto()   # waiting for the wake word
    CAPTURING = auto()   # wake word heard, buffering audio until VAD says the command ended


class VoiceListener:
    """
    Owns the single PyAudio input stream and the state machine over it.
    Construct ONCE (same lifecycle as Database/VectorStore); run() blocks
    the calling thread until stop(), so always start it on its own thread.
    """

    def __init__(
        self,
        transcriber: Transcriber,
        on_wake: Optional[Callable[[], None]] = None,
        on_command: Optional[Callable[[str], None]] = None,
        reference_buffer: PlaybackReferenceBuffer = default_playback_reference,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self._transcriber = transcriber
        self._on_wake = on_wake
        self._on_command = on_command
        self._reference_buffer = reference_buffer
        self._stop_event = stop_event or threading.Event()

        self._wakeword = WakeWordDetector()
        self._vad = VoiceActivityDetector()
        self._aec = EchoCanceller()

        self._state = _State.LISTENING
        self._command_chunks: List[np.ndarray] = []
        self._speech_start_sample: Optional[int] = None
        self._capture_started_at = 0.0

    def run(self) -> None:
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        try:
            while not self._stop_event.is_set():
                raw_bytes = stream.read(CHUNK, exception_on_overflow=False)
                pcm = np.frombuffer(raw_bytes, dtype=np.int16)

                # AEC runs on EVERY chunk in EVERY state -- not just while listening. If on_wake
                # plays a spoken acknowledgment, that audio starts during capture too, and without
                # cleaning it here it would leak straight into the command buffer.
                far = self._reference_buffer.pull(len(pcm))
                cleaned = self._aec.process(pcm, far)

                if self._state == _State.LISTENING:
                    self._tick_listening(cleaned)
                else:
                    self._tick_capturing(cleaned)
        except Exception as e:
            print(f"Got Error in Voice Listener as {e}")
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

    def stop(self) -> None:
        self._stop_event.set()

    # -- LISTENING state --

    def _tick_listening(self, pcm: np.ndarray) -> None:
        if self._wakeword.check(pcm):
            self._begin_capture()
            if self._on_wake is not None:
                self._on_wake()

    def _begin_capture(self) -> None:
        self._state = _State.CAPTURING
        # Reset now, not lazily -- VAD's reported sample indices need to start
        # at 0 exactly when this capture's own buffer does, or the two won't
        # line up when _finish_capture() slices the buffer by those indices.
        self._vad.reset()
        self._command_chunks = []
        self._speech_start_sample = None
        self._capture_started_at = time.monotonic()

    # -- CAPTURING state --

    def _tick_capturing(self, pcm: np.ndarray) -> None:
        self._command_chunks.append(pcm)
        events = self._vad.process(pcm)

        end_sample = None
        for event in events:
            if "start" in event and self._speech_start_sample is None:
                self._speech_start_sample = event["start"]
            if "end" in event:
                end_sample = event["end"]

        if end_sample is not None:
            self._finish_capture(end_sample)
            return

        elapsed = time.monotonic() - self._capture_started_at
        timed_out_waiting_for_speech = self._speech_start_sample is None and elapsed > COMMAND_START_TIMEOUT_SECONDS
        hit_max_duration = elapsed > VAD_MAX_COMMAND_SECONDS
        if timed_out_waiting_for_speech or hit_max_duration:
            # Deliberately discard rather than transcribe on either timeout: no confirmed speech
            # means there's nothing worth transcribing, and hitting the max-duration safety cap
            # means VAD likely never saw real speech end (continuous background noise) -- feeding
            # that to Whisper is far more likely to produce a hallucinated transcript than a
            # useful cut-off one.
            self._abandon_capture()

    def _finish_capture(self, end_sample: int) -> None:
        buffer = np.concatenate(self._command_chunks) if self._command_chunks else np.empty(0, dtype=np.int16)
        start = self._speech_start_sample if self._speech_start_sample is not None else 0
        utterance = buffer[start:end_sample]

        self._state = _State.LISTENING

        if len(utterance) == 0:
            return
        text = self._transcriber.transcribe_pcm(utterance)
        if text and self._on_command is not None:
            self._on_command(text)

    def _abandon_capture(self) -> None:
        self._state = _State.LISTENING
