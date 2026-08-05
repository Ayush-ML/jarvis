# This Script is responsible for storing the Agent Class
# The Agent class is responsible for taking in all Values and Configs and Submitting a Request to the Model
# It gives the specific Configs into the Request to make them match
# Importing Necessary Libraries
import requests
from typing import Dict, Any, List, Generator
from src.brain.request_schema import OpenAIRequestSchema
from src.core.config import TIMEOUT

# The Agent Class
class ModelClient:
    """
    Class that verifies the Request Schema and Posts a Request to the provider using that Schema
    """
    def __init__(self, request: OpenAIRequestSchema, base_url: str, api_key: str) -> None:
        """
        Initializes the ModelClient with the request schema, base URL, and API key.
        Args:
            request (OpenAIRequestSchema): The request schema containing the parameters for the request.
            base_url (str): The base URL of the provider's API.
            api_key (str): The API key for authentication with the provider.
        """
        self.request = request
        self.base_url = base_url.rstrip('/')  # Ensure no trailing slash in base_url
        self.api_key = api_key
        self.session = requests.Session()  # Create a session for connection pooling
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept" : "text/event-stream" if request.stream else "application/json"  # Accept event stream for streaming responses
        })
        
    def _endpoint(self) -> str:
        """
        Constructs the endpoint URL for the request.
        Returns:
            endpoint (str): The full endpoint URL.
        """
        return f"{self.base_url}/chat/completions"
    
    def _payload(self) -> Dict[str, Any]:
        """
        Constructs the payload for the request based on the request schema.
        Returns:
            payload (Dict[str, Any]): The payload to be sent in the request.
        """
        payload = {
            "model": self.request.model,
            "messages": self.request.messages,
            "stream": self.request.stream,
            "temperature": self.request.temperature,
            "max_tokens": self.request.max_tokens,
            "thinking": self.request.thinking,
            "strict": self.request.strict,
            "chat_template_kwargs": {
                "thinking": self.request.thinking
            }
        }
        if self.request.seed is not None:
            payload["seed"] = self.request.seed
        if self.request.tools:
            payload["tools"] = self.request.tools
            payload["tool_choice"] = self.request.tool_choice
        return payload
    
    def post(self) -> requests.Response | None:
        """
        Sends a POST request to the provider's API with the constructed payload.
        Returns:
            response (requests.Response): The response from the provider's API.
        Raises:
            requests.RequestException: If there is an error during the request.
        """
        try:
            response = self.session.post(
                url=self._endpoint(),
                json=self._payload(),
                timeout=TIMEOUT,
                stream=self.request.stream
            )
            response.raise_for_status()  # Raise an error for bad responses
            return response
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return None
    