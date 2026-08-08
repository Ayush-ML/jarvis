# This Script is responsible for the wakeword detection Model 
# It uses Openwakeword's Built in hey_jarvis model to detect the Wake word
# Low Confidence Threshold as it is a Small Model
# Importing Necessary Libraries
import time
import numpy as np
import pyaudio
import openwakeword
from src.core.config import SAMPLE_RATE, CHANNELS, CHUNK, THRESHOLD

def wakeword() -> None:
    """
    Function that handles the wakeword detection
    """
    
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
        while True:
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
                    time.sleep(0.5)
                    break
                
    except Exception as e:
        print(f"Got Error in Wakeword detection as {e}")
        
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
        return 