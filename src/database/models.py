# This Script defines the plain Data Models used across the Database Layer
# Kept separate from Repositories so other modules (memory, context) can
# depend on the shape of the data without pulling in sqlite3 itself
from dataclasses import dataclass
from typing import Optional
from src.core.message_types import TextContent


@dataclass
class Conversation:
    id: Optional[int]
    title: Optional[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    summary: Optional[str] = None
    summarized_through_message_id: int = 0  # highest message id already folded into `summary`


@dataclass
class Message:
    id: Optional[int]
    conversation_id: int
    role: str
    content: TextContent
    created_at: Optional[str] = None
    indexed: int = 0  # 0 = not yet in the vector store, 1 = indexed. See ConversationService.
