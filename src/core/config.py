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