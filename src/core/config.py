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

# --- Database / Memory / Context Settings ---
DB_PATH = os.getenv("DB_PATH", "data/jarvis.db") # SQLite database file location
MEMORY_TOP_K = 5 # How many memories the MemoryRetriever pulls in per turn
MEMORY_MIN_IMPORTANCE = 0.0 # Memories below this importance are filtered out of retrieval
MAX_CONTEXT_TOKENS = 6000 # Approx. token budget ContextManager trims recent history to