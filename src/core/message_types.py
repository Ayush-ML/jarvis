"""Shared types for OpenAI-compatible chat messages."""
from typing import Literal, TypedDict


class TextContent(TypedDict):
    type: Literal["text"]
    text: str


class ImageURLContent(TypedDict):
    type: Literal["image_url"]
    image_url: str

class AudioURLContent(TypedDict):
    type: Literal["audio_url"]
    audio_url: str

class VideoURLContent(TypedDict):
    type: Literal["video_url"]
    video_url: str

MessageContent = TextContent | ImageURLContent | AudioURLContent | VideoURLContent

class ChatMessage(TypedDict):
    role: str
    content: MessageContent
