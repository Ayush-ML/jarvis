# This Script is responsible for Semantic Recall across ALL past sessions
# Thin wrapper around VectorStore -- ContextManager depends on this interface, not on
# Chroma directly, so the underlying vector store can change without touching brain/context_manager.py
from typing import List, NamedTuple, Optional
from src.memory.vector_store import VectorStore


class RecalledMessage(NamedTuple):
    conversation_id: int
    role: str
    content: str


class MemoryRetriever:
    def __init__(self, vector_store: VectorStore, top_k: int = 5) -> None:
        self.vector_store = vector_store
        self.top_k = top_k

    def retrieve(self, query: str, exclude_conversation_id: Optional[int] = None) -> List[RecalledMessage]:
        if not query.strip():
            return []
        hits = self.vector_store.search(query, top_k=self.top_k, exclude_conversation_id=exclude_conversation_id)
        return [RecalledMessage(h["conversation_id"], h["role"], h["content"]) for h in hits]
