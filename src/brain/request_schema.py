# This Script is Responsible for the Request Schema Class
# The Request Schema Class is responsible for defining the structure of the request that will be sent to the Nvidia NIM Client
# It is the main class that decides the Request's Parameters like Streaming, Temperature, Max Tokens etc
# Importing Necessary Libraries
from src.core.config import STREAM, TEMPERATURE, MAX_TOKENS, TOOL_CHOICE, THINKING, BASE_URL, MODEL, API_KEY, STRICT
from dataclasses import dataclass, field 
from typing import Any, List, Optional, Dict
import numpy as np
from src.core.message_types import ChatMessage

# Create the Requests Dataclass to Store the Request Parameters
@dataclass
class OpenAIRequestSchema:
    """
    Dataclass to Store the Structure of the Request that will be sent to the Provider, OpenAI Compatible in this case.

    IMPORTANT: this is a STATELESS per-request spec, not a conversation buffer.
    `messages` should always be freshly built per turn by ContextManager.build()
    and passed in at construction time -- never mutate `.messages` on a shared
    instance across turns, or history/memory management below this class
    (SQLite, MemoryRetriever) is bypassed entirely.
    """
    model: str = MODEL
    messages: List[ChatMessage] = field(default_factory=list) # Context of the Conversation
    stream: bool = STREAM
    temperature: float = TEMPERATURE
    max_tokens: int = MAX_TOKENS
    tool_choice: str = TOOL_CHOICE
    thinking: bool = THINKING
    seed: Optional[int] = None   # Optional seed for reproducibility
    tools: List[Dict[str, Any]] = field(default_factory=list)  # Tools for the model to use
    strict: bool = STRICT 
    additional_params: bool = field(init=False, default=False) # Whether to Allow Additional Parameters or not, Only Works if Strict is False
    
    def __post_init__(self):
        self.additional_params = not self.strict  # Set additional_params based on strict
        if self.seed:
            np.random.seed(seed=self.seed)  # Set the random seed for reproducibility