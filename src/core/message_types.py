"""Shared types for OpenAI-compatible chat messages."""
from typing import Literal, TypedDict


class TextContent(TypedDict):
    type: Literal["text"]
    text: str


class ChatMessage(TypedDict):
    role: str
    content: TextContent
