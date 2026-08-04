# This Script is Responsible for the Agent Class
# The Agent Class is responsible for Posting a Request to the Nvidia NIM Client and Recieving a Response Back
# It is the main class that decides the Agent's Parameters like Streaming, Temperature, Max Tokens etc
# Importing Necessary Libraries
from src.core.config import STREAM, TEMPERATURE, MAX_TOKENS, TOOL_CHOICE, THINKING, BASE_URL, MODEL, API_KEY, STRICT
from dataclasses import dataclass, field 
from typing import Any, List, Dict, Optional
import numpy as np

# Create the Requests Dataclass to Store the Request Parameters
@dataclass
class RequestSchema:
    model: str = MODEL
    messages: List[Dict[str, str]] = field(default_factory=list) # Context of the Converation
    base_url: str = BASE_URL
    api_key: str = API_KEY
    stream: bool = STREAM
    temperature: float = TEMPERATURE
    max_tokens: int = MAX_TOKENS
    tool_choice: str = TOOL_CHOICE
    thinking: bool = THINKING
    seed: Optional[int] = None   # Optional seed for reproducibility
    tools: List[Dict[str, Any]] = field(default_factory=list)  # Tools for the model to use
    strict: bool = STRICT 
    additional_params: bool = False if strict else True # Whether to Allow Additional Parameters or not, Only Works if Strict is False
    
    def __post_init__(self):
        self.base_url.rstrip('/')  # Ensure no trailing slash in base_url
        if self.seed:
            np.random.seed(seed=self.seed)  # Set the random seed for reproducibility