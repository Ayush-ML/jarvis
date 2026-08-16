# This Script is responsible for the two shared signals that make Jarvis interruptible (barge-in)
# while it's speaking:
#   - speaking_event: SET by tts() for the duration of playback, CLEARED when playback ends
#     (normally or interrupted). VoiceListener watches this to know when to switch from normal
#     wake-word-gated listening into barge-in monitoring (VAD without requiring the wake word --
#     appropriate ONLY while Jarvis itself is talking, since any speech during Jarvis's own turn
#     is meaningfully likely to be the user trying to interrupt; the same isn't true during idle
#     listening, which is why wake-word gating still applies there).
#   - interrupt_event: SET by VoiceListener the moment it confirms real speech during SPEAKING
#     (i.e. a genuine interruption, not just noise). tts() checks this to cut playback short.
#     CLEARED automatically by tts() at the start of every call -- callers never need to manage
#     this themselves, which avoids a whole class of "forgot to clear before the next call" bugs.
# Both are managed entirely by tts.py and listener.py; nothing else in the codebase should need
# to touch these directly.
import threading

speaking_event = threading.Event()
interrupt_event = threading.Event()
