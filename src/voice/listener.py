# This Script is responsible for the actual voice loop: wake detection -> command capture ->
# transcription, PLUS barge-in monitoring while Jarvis is speaking, composing every primitive in
# this package (WakeWordDetector, EchoCanceller, VoiceActivityDetector, Transcriber,
# PlaybackReferenceBuffer) around ONE PyAudio input stream.
#
# THREE STATES:
#   LISTENING  -- waiting for the wake word (gated: ordinary ambient speech should NOT trigger this)
#   SPEAKING   -- Jarvis is currently talking (barge_in.speaking_event is set by tts()). Monitors
#                 VAD directly, no wake word needed -- any confirmed real speech during Jarvis's
#                 own turn is meaningfully likely to be an interruption. Retains only a BOUNDED
#                 pre-roll of recent audio (SPEAKING_MONITOR_SECONDS), not the whole TTS duration,
#                 since most of it gets discarded if nobody interrupts.
#   CAPTURING  -- buffering a command (either from a normal wake-word trigger, or from a confirmed
#                 barge-in interruption) until VAD reports the utterance ended.
#
# CALLBACK CONTRACT: on_wake and on_command run SYNCHRONOUSLY on this loop's own thread. A slow
# handler blocks stream.read() from being called during that time -- PyAudio silently drops audio
# captured in that gap (exception_on_overflow=False, the same trade-off the original wakeword()
# already accepted). Dispatch slow work to another thread from inside your callback if you want
# the listener to keep listening while handling an event -- this class does not do that for you.
# Note this matters LESS for barge-in specifically: tts() playback already runs independently of
# this loop (that's the whole point), so Jarvis being interruptible doesn't depend on on_command
# itself being non-blocking -- only on whatever drives tts() being reachable while it plays.
import time
import threading
from collections import deque
import numpy as np
import pyaudio
from enum import Enum, auto
from typing import Callable, Deque, Optional
from src.voice.wakeword import WakeWordDetector
from src.voice.vad import VoiceActivityDetector
from src.voice.aec import EchoCanceller
from src.voice.transcriber import Transcriber
from src.voice.playback_reference import default_playback_reference, PlaybackReferenceBuffer
from src.voice import barge_in
from src.core.config import (
    SAMPLE_RATE, CHANNELS, CHUNK,
    COMMAND_START_TIMEOUT_SECONDS, VAD_MAX_COMMAND_SECONDS, SPEAKING_MONITOR_SECONDS,
)

_SPEAKING_MONITOR_MAX_SAMPLES = int(SPEAKING_MONITOR_SECONDS * SAMPLE_RATE)


class _State(Enum):
    LISTENING = auto()
    SPEAKING = auto()
    CAPTURING = auto()


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
        self._command_chunks: Deque[np.ndarray] = deque()
        self._dropped_samples = 0  # samples trimmed from the FRONT of _command_chunks during SPEAKING monitoring -- see _trim_speaking_buffer
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
                # or a response plays audio, that audio leaks straight into whatever buffer is
                # active unless it's cleaned here first.
                far = self._reference_buffer.pull(len(pcm))
                cleaned = self._aec.process(pcm, far)

                self._sync_speaking_state()

                if self._state == _State.LISTENING:
                    self._tick_listening(cleaned)
                elif self._state == _State.SPEAKING:
                    self._tick_speaking(cleaned)
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

    def _sync_speaking_state(self) -> None:
        """
        Enters/exits SPEAKING based on barge_in.speaking_event, which tts() owns.
        Only acts from/to LISTENING -- if Jarvis somehow starts talking while a
        command capture is still in progress, that's a caller-side ordering
        issue this class doesn't try to resolve; it just keeps capturing.
        """
        if self._state == _State.LISTENING and barge_in.speaking_event.is_set():
            self._begin_speaking_monitor()
        elif self._state == _State.SPEAKING and not barge_in.speaking_event.is_set():
            # Jarvis finished speaking on its own with no interruption detected.
            self._state = _State.LISTENING

    # -- LISTENING state --

    def _tick_listening(self, pcm: np.ndarray) -> None:
        if self._wakeword.check(pcm):
            self._begin_capture()
            if self._on_wake is not None:
                self._on_wake()

    # -- SPEAKING state (barge-in monitoring) --

    def _begin_speaking_monitor(self) -> None:
        self._state = _State.SPEAKING
        # Fresh VAD state for this speaking session, same reasoning as _begin_capture(): reported
        # sample indices need to start at 0 exactly when this session's buffer does.
        self._vad.reset()
        self._command_chunks = deque()
        self._dropped_samples = 0
        self._speech_start_sample = None

    def _tick_speaking(self, pcm: np.ndarray) -> None:
        self._command_chunks.append(pcm)
        self._trim_speaking_buffer()

        events = self._vad.process(pcm)
        for event in events:
            if "start" in event:
                # Confirmed real speech while Jarvis is talking -- this IS the interruption.
                barge_in.interrupt_event.set()
                self._speech_start_sample = event["start"]  # RAW, uncorrected -- _finish_capture applies the _dropped_samples offset uniformly to both boundaries
                self._state = _State.CAPTURING
                self._capture_started_at = time.monotonic()
                # Deliberately NOT calling _begin_capture() here -- that would reset _command_chunks
                # and lose the pre-roll audio, and would reset VAD, losing its "already in speech"
                # state right when we need it to keep tracking toward this same utterance's end.
                return

    def _trim_speaking_buffer(self) -> None:
        """Bounds retained audio to SPEAKING_MONITOR_SECONDS while monitoring, tracking the drop offset for later index correction."""
        total = sum(len(c) for c in self._command_chunks)
        while total > _SPEAKING_MONITOR_MAX_SAMPLES and len(self._command_chunks) > 1:
            dropped = self._command_chunks.popleft()
            self._dropped_samples += len(dropped)
            total -= len(dropped)

    # -- CAPTURING state --

    def _begin_capture(self) -> None:
        self._state = _State.CAPTURING
        self._vad.reset()
        self._command_chunks = deque()
        self._dropped_samples = 0
        self._speech_start_sample = None
        self._capture_started_at = time.monotonic()

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
        # _dropped_samples is 0 for a normal wake-word capture (no trimming ever occurs on that
        # path), so this offset is a no-op there. For a barge-in capture it's whatever got trimmed
        # during SPEAKING monitoring -- applied uniformly to BOTH boundaries here, once, rather than
        # pre-correcting only one of them at the point each was recorded (start and end are set in
        # two different methods, potentially one call apart, so correcting them inconsistently is
        # exactly the kind of thing that quietly breaks only the less-common code path).
        raw_start = self._speech_start_sample if self._speech_start_sample is not None else 0
        start = max(raw_start - self._dropped_samples, 0)
        end = max(end_sample - self._dropped_samples, 0)
        utterance = buffer[start:end]

        self._state = _State.LISTENING

        if len(utterance) == 0:
            return
        text = self._transcriber.transcribe_pcm(utterance)
        if text and self._on_command is not None:
            self._on_command(text)

    def _abandon_capture(self) -> None:
        self._state = _State.LISTENING
