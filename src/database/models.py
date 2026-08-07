# This Script defines the plain Data Models used across the Database Layer
# Kept separate from Repositories so other modules (memory, context) can
# depend on the shape of the data without pulling in sqlite3 itself
from dataclasses import dataclass
from typing import Optional


@dataclass
class Conversation:
    id: Optional[int]
    title: Optional[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Message:
    id: Optional[int]
    conversation_id: int
    role: str
    content: str
    created_at: Optional[str] = None
