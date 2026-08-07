# This Script is responsible for Writing new Memories
# Deliberately separate from the Retriever: writes are rare and explicit
# (a skill, a manual /remember command, a future extraction step), while
# reads happen on every single turn -- keeping them apart keeps both small
from typing import Optional
from src.database.repository import MemoryRepository
from src.database.models import Memory


class MemoryStore:
    """Thin write-side wrapper around MemoryRepository."""

    def __init__(self, memory_repo: MemoryRepository) -> None:
        self.memory_repo = memory_repo

    def remember(
        self,
        content: str,
        kind: str = "fact",
        importance: float = 0.5,
        source_message_id: Optional[int] = None,
    ) -> Memory:
        return self.memory_repo.add(content, kind, importance, source_message_id)
