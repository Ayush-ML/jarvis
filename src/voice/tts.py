# This Script is responsible for Text to Speech using Edge TTS
# Decodes Edge TTS's compressed stream via ffmpeg into raw PCM matching this pipeline's format
# (16kHz mono int16), then owns playback itself through a PyAudio output stream instead of
# handing off to ffplay -- so the exact samples reaching the speaker are also available as the
# AEC reference signal (see src/voice/playback_reference.py). ffmpeg auto-detects the input
# codec/rate from the stream itself, so this doesn't need to know or assume Edge TTS's native
# output format -- only the desired output format is specified.
# It uses a British Voice to best capture JARVIS along with a slower and deeper voice to make it sound more like JARVIS
# Importing Necessary Libraries
import asyncio
import numpy as np
import pyaudio
import edge_tts
from src.core.config import VOICE, RATE, PITCH, SAMPLE_RATE, CHANNELS, CHUNK
from src.voice.playback_reference import default_playback_reference, PlaybackReferenceBuffer

_BYTES_PER_SAMPLE = 2  # int16
_audio = pyaudio.PyAudio()  # Host object is expensive to init -- shared across calls; individual Streams are opened/closed per call


# The Async Function to stream, decode, and play the Audio using Edge TTS
async def tts(
    text: str,
    voice: str = VOICE,
    rate: str = RATE,
    pitch: str = PITCH,
    reference_buffer: PlaybackReferenceBuffer = default_playback_reference,
) -> None:
    """
    Stream Edge TTS audio through ffmpeg (decode + resample to 16kHz mono int16),
    play it via a PyAudio output stream, and push every played chunk into
    `reference_buffer` so AEC has a real signal to cancel against.
    Args:
        text: The text to be converted to speech.
        voice: The voice to be used for TTS.
        rate: The rate of the voice.
        pitch: The pitch of the voice.
        reference_buffer: Where played PCM is pushed for AEC. Defaults to the
            shared buffer every AEC consumer reads from -- override only for
            testing or a deliberately separate playback path.
    """
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)

    ffmpeg_process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-loglevel", "quiet",
        "-i", "pipe:0",
        "-f", "s16le",
        "-ar", str(SAMPLE_RATE),
        "-ac", str(CHANNELS),
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
    )

    output_stream = _audio.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        output=True,
    )

    async def feed_ffmpeg() -> None:
        """Pipes Edge TTS's compressed chunks into ffmpeg's stdin as they arrive."""
        try:
            async for chunk in communicate.stream():
                if chunk["type"] != "audio":
                    continue
                if ffmpeg_process.stdin is None:
                    break
                ffmpeg_process.stdin.write(chunk["data"])
                await ffmpeg_process.stdin.drain()
        finally:
            if ffmpeg_process.stdin is not None:
                ffmpeg_process.stdin.close()

    async def read_and_play() -> None:
        """Reads decoded PCM from ffmpeg's stdout, plays it, and mirrors it into reference_buffer."""
        loop = asyncio.get_event_loop()
        read_bytes = CHUNK * _BYTES_PER_SAMPLE
        while True:
            pcm_bytes = await ffmpeg_process.stdout.read(read_bytes)
            if not pcm_bytes:
                break
            pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
            reference_buffer.push(pcm)
            # PyAudio's write() blocks until the device has buffer room -- run it off
            # the event loop thread so it doesn't stall feed_ffmpeg() running concurrently
            await loop.run_in_executor(None, output_stream.write, pcm_bytes)

    try:
        await asyncio.gather(feed_ffmpeg(), read_and_play())
    finally:
        output_stream.stop_stream()
        output_stream.close()
        await ffmpeg_process.wait()

# A Small Function to handle the Asynchronous Running of the Main function
async def play(text: str) -> None:
    """
    Plays the Given Text as Audio in the Coded Voice
    Args:
        text: A String of what you want the TTS engine to sat
    """

    await tts(text=text)
