# This Script is responsible for Storing all Hardcoded Values and Configurations for the Jarvis Project
# This is Done to Modularize the Code
# Make it more Readable and Changeable without having to go through the entire codebase or breaking everything
# Importing Necessary Libraries
import os
from dotenv import load_dotenv

load_dotenv() # Load the .env file

STREAM = True # Whether to Stream the Response or Not
TEMPERATURE = 0.8 # The Temperature of the Model, Higher the Temperature, More Creative or Varied the Response
MAX_TOKENS = 32564
TOOL_CHOICE = 'auto' # Whether the Model uses a Tool or Not, Auto means the Model will Decide on its own, required means it will use a Tool, none means it will not use a Tool
THINKING = True # Whether the Model will Think or Not, Thinking is the Process of the Model Deciding on its own what to do, and how to do it, without any Human Intervention
BASE_URL = os.getenv("BASE_URL") # The Base URL to post a request to
MODEL = "moonshotai/kimi-k2.6" # The Model that is used to generate responses
API_KEY = os.getenv("API_KEY") # The API Key for the Provider, Stored in the .env file for Security Reasons
STRICT = True # Whether to Strictly Follow the Tool Schema  or not
PROVIDER = "openai" # The Format that the Provider uses, Mainly OpenAI, Anthropic and Google
TIMEOUT = 60 # The Timeout for the Request, in Seconds
RATE_LIMIT_RPM = 40 # Max requests per minute to the Model Provider, enforced by RateLimiter
TOP_P = 0.9 # The Top P value for the Model, Higher the Top P, More Creative or Varied the Response
DB_PATH = "data/jarvis.db" # SQLite database file location (conversation history only)
MAX_CONTEXT_TOKENS = 6000 # Approx. token budget ContextManager trims recent history to
HISTORY_WINDOW = 12 # Recent raw turns kept verbatim in context; older turns fall out and get folded into the rolling summary instead
SUMMARY_BATCH_SIZE = 12 # Once this many turns have fallen out of HISTORY_WINDOW without being summarized, fold them into the conversation's summary
SOUL_PATH = "data/SOUL.md" # Jarvis's system prompt / persona, hand-edited
USER_PROFILE_PATH = "data/USER.md" # User profile, injected if present
VECTOR_STORE_PATH = "data/chroma" # Local ChromaDB persistence directory
VECTOR_COLLECTION_NAME = "jarvis_messages" # Chroma collection name
SEMANTIC_TOP_K = 5 # How many past-session messages MemoryRetriever surfaces per turn
SEMANTIC_OVERFETCH = 4 # Multiplier on top_k fetched from Chroma before recency re-ranking trims back to top_k
SEMANTIC_MAX_DISTANCE = 0.45 # Cosine distance floor (0=identical, 2=opposite) -- hits worse than this are dropped, not just ranked low
SEMANTIC_RECENCY_HALFLIFE_DAYS = 30 # A recalled message's relevance weight halves every this-many days
VOICE = "en-GB-RyanNeural" # The Voice used to Generate the Text To Speech Audio
RATE = "-5%" # The Rate of the Voice, Lower the Rate, Slower the Voice
PITCH = "-3Hz" # The Pitch of the Voice, Lower the Pitch, Deeper the Voice
SAMPLE_RATE = 16000 # Sample Rate for the Audio Stream
CHANNELS = 1 # Mono Channel Audio Stream
CHUNK = 1280 # 80 Ms at 16 kHz Sample Rate
THRESHOLD = 0.3 # Model Confidence Threshold for a confirmed Trigger
STT_MODEL_SIZE = "small" # faster-whisper model size -- "small" chosen for 8GB RAM / CPU-only hardware, bump to "medium"+ only with a GPU or more headroom
STT_DEVICE = "cpu" # No CUDA/ROCm path on this hardware -- CPU inference only
STT_COMPUTE_TYPE = "int8" # Quantized for CPU speed and lower memory use; "float32" is more accurate but ~4x slower on CPU
VAD_THRESHOLD = 0.5 # Silero's own recommended default -- speech probabilities above this are treated as speech
VAD_SILENCE_MS = 800 # Confirmed silence duration before a speech segment is considered ENDED (a command-capture UX choice, deliberately more patient than Silero's own 100ms default which is tuned for offline segment-finding, not "wait until the user is clearly done talking")
VAD_SPEECH_PAD_MS = 100 # Silero's own edge-padding on reported start/end timestamps, guarding against the ~32ms detection latency clipping the first phoneme -- NOT a substitute for a caller-side rolling pre-buffer (see VoiceActivityDetector docstring)
AEC_STREAM_DELAY_MS = 0 # Hint for AEC3's delay estimator: ms between writing audio to the speaker buffer and the matching echo appearing in mic capture. Left at 0 (let AEC3 self-estimate) rather than a guessed value -- once tts.py owns playback directly, measure this for real with pywebrtc-audio's own examples/e2e_verify.py and set it here as a convergence-speed hint, not a hard requirement
COMMAND_START_TIMEOUT_SECONDS = 5 # If VAD hasn't confirmed speech this long after wake-word detection, abandon capture and return to listening -- probably a false trigger or the user changed their mind
VAD_MAX_COMMAND_SECONDS = 15 # Hard safety cap on total command-capture duration regardless of VAD state -- guards against a misfiring VAD never reporting 'end' on continuous background noise (TV, music)
SPEAKING_MONITOR_SECONDS = 1.0 # How much recent audio VoiceListener retains as pre-roll while monitoring for a barge-in interruption during SPEAKING state -- bounded, not the full TTS duration, since most of it gets discarded if nobody interrupts
MCP_CONFIG_PATH = "data/mcp_servers.json" # JSON config listing MCP servers to connect to -- mirrors the standard "mcpServers" object convention (same shape as Claude Desktop's config)
MCP_CONNECT_TIMEOUT_SECONDS = 15 # Max time to wait for a single MCP server to connect before giving up on it and moving on to the rest
MCP_MAX_INPUT_REQUIRED_ROUNDS = 10 # Safety cap on elicitation retry rounds per tool call -- matches mcp.Client's own default, kept the same for familiarity even though ClientSessionGroup needs its own hand-rolled loop
