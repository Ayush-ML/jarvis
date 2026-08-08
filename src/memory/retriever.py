# This Script is responsible for Semantic Recall across ALL past sessions
# Thin wrapper around VectorStore -- ContextManager depends on this interface, not on
# Chroma directly, so the underlying vector store can change without touching brain/context_manager.py
#
# Two things happen here that VectorStore itself doesn't do:
#   - over-fetch + recency re-ranking (pure similarity can surface a topically-close
#     message from months ago over a more relevant one from yesterday)
#   - carrying VectorStore's max_distance floor through as a real config default,
#     so "no good matches" returns nothing instead of the 5 best-of-a-bad-bunch
from datetime import datetime, timezone
from typing import List, NamedTuple, Optional
from src.memory.vector_store import VectorStore
from src.core.config import SEMANTIC_TOP_K, SEMANTIC_OVERFETCH, SEMANTIC_MAX_DISTANCE, SEMANTIC_RECENCY_HALFLIFE_DAYS


class RecalledMessage(NamedTuple):
    conversation_id: int
    role: str
    content: str


class MemoryRetriever:
    def __init__(
        self,
        vector_store: VectorStore,
        top_k: int = SEMANTIC_TOP_K,
        max_distance: float = SEMANTIC_MAX_DISTANCE,
        recency_halflife_days: float = SEMANTIC_RECENCY_HALFLIFE_DAYS,
    ) -> None:
        self.vector_store = vector_store
        self.top_k = top_k
        self.max_distance = max_distance
        self.recency_halflife_days = recency_halflife_days

    def retrieve(self, query: str, exclude_conversation_id: Optional[int] = None) -> List[RecalledMessage]:
        if not query.strip():
            return []

        # Over-fetch past top_k so recency re-ranking has something to work
        # with -- otherwise "top_k by pure similarity" is all we could ever return.
        hits = self.vector_store.search(
            query,
            top_k=self.top_k * SEMANTIC_OVERFETCH,
            exclude_conversation_id=exclude_conversation_id,
            max_distance=self.max_distance,
        )
        if not hits:
            return []

        ranked = sorted(hits, key=self._combined_score, reverse=True)[: self.top_k]
        return [RecalledMessage(h["conversation_id"], h["role"], h["content"]) for h in ranked]

    def _combined_score(self, hit) -> float:
        similarity = 1.0 - hit["distance"]  # cosine distance -> similarity, roughly [-1, 1]
        return similarity * self._recency_weight(hit["created_at"])

    def _recency_weight(self, created_at: Optional[str]) -> float:
        """
        Exponential decay: weight halves every `recency_halflife_days`. Messages
        with no timestamp (shouldn't happen post-fix, but defensively) get a
        neutral weight rather than being penalized for missing data.
        """
        if not created_at:
            return 1.0
        try:
            created = datetime.fromisoformat(created_at.replace(" ", "T")).replace(tzinfo=timezone.utc)
        except ValueError:
            return 1.0
        age_days = max((datetime.now(timezone.utc) - created).total_seconds() / 86400, 0)
        return 0.5 ** (age_days / self.recency_halflife_days)
