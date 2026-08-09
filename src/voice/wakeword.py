# This Script is responsible for the wakeword detection Model 
# It uses Openwakeword's Built in hey_jarvis model to detect the Wake word
# Low Confidence Threshold as it is a Small Model
# Importing Necessary Libraries
import time
import threading
import numpy as np
import pyaudio
import openwakeword
from typing import Callable, Optional
from src.core.config import SAMPLE_RATE, CHANNELS, CHUNK, THRESHOLD

def wakeword(on_detected: Callable[[], None], stop_event: Optional[threading.Event] = None) -> None:
    """
    Function that handles the wakeword detection. Blocks the calling thread until
    `stop_event` is set, so this should always be started on its own thread, e.g.
    threading.Thread(target=wakeword, args=(on_detected, stop_event), daemon=True).start()

    Args:
        on_detected: called with no arguments every time the wake word is heard.
            This is the only way anything outside this function learns detection
            happened -- previously nothing did (see below).
        stop_event: set this from another thread to stop listening and return
            cleanly. If omitted, a fresh Event is created and this effectively
            runs forever -- only fine if you're okay killing the whole thread to stop it.
    """
    if stop_event is None:
        stop_event = threading.Event()

    model = openwakeword.model.Model(
        wakeword_models=["hey_jarvis"], # Initialize Model in ONNX Format
        inference_framework="onnx",
    )
    
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=CHANNELS, # Initialize Audio Stream
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    try:
        while not stop_event.is_set():
            audio_bytes = stream.read(
                CHUNK,
                exception_on_overflow=False,
            )
            pcm = np.frombuffer(  # Read Audio
                audio_bytes,
                dtype=np.int16,
            )

            predictions = model.predict(pcm) # Predict on Audio

            for _, score in predictions.items():
                if score >= THRESHOLD:
                    model.reset()
                    on_detected()  # FIX: this is the only line that actually notifies the app -- previously nothing did
                    time.sleep(0.5)
                    break
                
    except Exception as e:
        print(f"Got Error in Wakeword detection as {e}")
        
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        return 