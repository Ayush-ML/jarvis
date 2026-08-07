# This Script is responsible for Retrieving Memories relevant to the current turn
# It sits between the raw MemoryRepository (storage) and the ContextManager (assembly),
# so the ranking/filtering strategy can change later without touching either side
from typing import List
from src.database.repository import MemoryRepository
from src.database.models import Memory


class MemoryRetriever:
    """
    Retrieves the memories most relevant to a given query. Currently backed
    by SQLite FTS5/BM25 keyword search; swap the internal `search` call for
    an embedding-based lookup later without changing the ContextManager.
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        top_k: int = 5,
        min_importance: float = 0.0,
    ) -> None:
        self.memory_repo = memory_repo
        self.top_k = top_k
        self.min_importance = min_importance

    def retrieve(self, query: str) -> List[Memory]:
        if not query.strip():
            return []
        candidates = self.memory_repo.search(query, top_k=self.top_k)
        return [m for m in candidates if m.importance >= self.min_importance]
