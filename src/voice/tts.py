
# This Script is responsible for Text to Speech using Edge TTS
# It streams the Audio Directly to FFmpeg for PLayback
# The Playback is Asynchronous so Other Tasks can be performed while the Audio is being Played
# It uses a British Voice to best capture JARVIS along with a slower and deeper voice to make it sound more like JARVIS
# Importing Necessary Libraries
import asyncio
import edge_tts
from src.core.config import VOICE, RATE, PITCH

# The Async Function to stream and play the Audio using Edge TTS
async def tts(text: str, voice: str = VOICE, rate: str = RATE, pitch: str = PITCH) -> None:
    """
    Stream Edge TTS audio directly into FFplay.
    Edge TTS produces compressed audio data.
    FFplay handles decoding and playback.
    Args:
        text: The text to be converted to speech.
        voice: The voice to be used for TTS.
        rate: The rate of the voice.
        pitch: The pitch of the voice.
    """

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    process = await asyncio.create_subprocess_exec(
        "ffplay",
        "-nodisp",
        "-autoexit",
        "-loglevel",
        "quiet",
        "-i",
        "pipe:0",
        stdin=asyncio.subprocess.PIPE
    )
    try:
        async for chunk in communicate.stream():
            if chunk["type"] != "audio":
                continue
            if process.stdin is None:
                break
            process.stdin.write(chunk["data"])
            await process.stdin.drain()
    finally:
        if process.stdin is not None:
            process.stdin.close()
        await process.wait()

# A Small Function to handle the Asynchronous Running of the Main function
async def play(text: str) -> None:
    """
    Plays the Given Text as Audio in the Coded Voice
    Args:
        text: A String of what you want the TTS engine to sat
    """
    
    await asyncio.run(tts(text=text))