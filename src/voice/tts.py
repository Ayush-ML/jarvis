# This Script is responsible for Text to Speech using Edge TTS
# Decodes Edge TTS's compressed stream via ffmpeg into raw PCM matching this pipeline's format
# (16kHz mono int16), then owns playback itself through a PyAudio output stream instead of
# handing off to ffplay -- so the exact samples reaching the speaker are also available as the
# AEC reference signal (see src/voice/playback_reference.py). ffmpeg auto-detects the input
# codec/rate from the stream itself, so this doesn't need to know or assume Edge TTS's native
# output format -- only the desired output format is specified.
#
# INTERRUPTIBLE BY DESIGN: sets barge_in.speaking_event for the duration of playback and checks
# barge_in.interrupt_event throughout -- see src/voice/barge_in.py for the full signaling
# contract and src/voice/listener.py for who actually sets interrupt_event (VoiceListener,
# on confirming real speech while Jarvis is talking).
# It uses a British Voice to best capture JARVIS along with a slower and deeper voice to make it sound more like JARVIS
# Importing Necessary Libraries
import asyncio
import numpy as np
import pyaudio
import edge_tts
from src.core.config import VOICE, RATE, PITCH, SAMPLE_RATE, CHANNELS, CHUNK
from src.voice.playback_reference import default_playback_reference, PlaybackReferenceBuffer
from src.voice import barge_in

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

    Interruptible: if barge_in.interrupt_event gets set while this is playing
    (VoiceListener sets it on confirming real speech during playback), playback
    is cut short -- both the ffmpeg decode and the audio stream are stopped,
    not just "no more chunks queued".
    Args:
        text: The text to be converted to speech.
        voice: The voice to be used for TTS.
        rate: The rate of the voice.
        pitch: The pitch of the voice.
        reference_buffer: Where played PCM is pushed for AEC. Defaults to the
            shared buffer every AEC consumer reads from -- override only for
            testing or a deliberately separate playback path.
    """
    barge_in.interrupt_event.clear()  # every call starts clean, regardless of any previous call's outcome

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

    barge_in.speaking_event.set()

    async def feed_ffmpeg() -> None:
        """
        Pipes Edge TTS's compressed chunks into ffmpeg's stdin as they arrive.
        Checks interrupt_event itself (not just read_and_play) -- otherwise this
        keeps feeding however much of the response is left even after playback
        has audibly stopped, which delays asyncio.gather() below from completing
        and therefore delays the finally block's actual stop/kill from running.
        """
        try:
            async for chunk in communicate.stream():
                if barge_in.interrupt_event.is_set():
                    break
                if chunk["type"] != "audio":
                    continue
                if ffmpeg_process.stdin is None:
                    break
                ffmpeg_process.stdin.write(chunk["data"])
                await ffmpeg_process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass  # ffmpeg exited on its own (e.g. malformed chunk) -- not this function's problem to raise further
        finally:
            if ffmpeg_process.stdin is not None and not ffmpeg_process.stdin.is_closing():
                ffmpeg_process.stdin.close()

    async def read_and_play() -> None:
        """Reads decoded PCM from ffmpeg's stdout, plays it, and mirrors it into reference_buffer."""
        loop = asyncio.get_event_loop()
        read_bytes = CHUNK * _BYTES_PER_SAMPLE
        try:
            while not barge_in.interrupt_event.is_set():
                pcm_bytes = await ffmpeg_process.stdout.read(read_bytes)
                if not pcm_bytes:
                    break
                pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
                reference_buffer.push(pcm)
                # PyAudio's write() blocks until the device has buffer room -- run it off
                # the event loop thread so it doesn't stall feed_ffmpeg() running concurrently
                await loop.run_in_executor(None, output_stream.write, pcm_bytes)
        except OSError:
            pass  # output_stream may already be mid-stop from the interrupt path below

    try:
        await asyncio.gather(feed_ffmpeg(), read_and_play())
    finally:
        # stop_stream() aborts whatever's still mid-flight in the OS audio buffer rather than
        # draining it -- this is what actually makes the cutoff prompt, not just "stopped
        # sending new chunks". Exact residual latency still depends on the OS driver, not
        # something this code can fully eliminate.
        output_stream.stop_stream()
        output_stream.close()
        if barge_in.interrupt_event.is_set():
            ffmpeg_process.kill()
        await ffmpeg_process.wait()
        barge_in.speaking_event.clear()
        # Stale reference audio left in the buffer after playback stops would make AEC try to
        # cancel an echo that's no longer actually playing -- clear it so the next mic capture
        # isn't processed against a reference signal describing audio that already ended.
        reference_buffer.reset()

# A Small Function to handle the Asynchronous Running of the Main function
async def play(text: str) -> None:
    """
    Plays the Given Text as Audio in the Coded Voice
    Args:
        text: A String of what you want the TTS engine to sat
    """

    await tts(text=text)
