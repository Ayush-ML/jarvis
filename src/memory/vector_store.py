# This Script is responsible for the local Vector Store used for Semantic Search across ALL sessions
# Backed by ChromaDB running fully locally: persisted to disk, embedded on-device via Chroma's
# bundled ONNX MiniLM model. No network call, no API key, no dependency on the chat provider --
# swap `_embedding_fn` for a different sentence-transformers/FAISS setup later if you want to,
# nothing outside this file needs to know how the vector search works internally.
import chromadb
from typing import List, Optional, TypedDict
from src.core.config import VECTOR_STORE_PATH, VECTOR_COLLECTION_NAME

# Only these roles get embedded. Tool calls / system messages would otherwise
# get indexed too and can surface as noise in recall for an unrelated turn.
INDEXABLE_ROLES = {"user", "assistant"}


class RecalledHit(TypedDict):
    message_id: int
    conversation_id: int
    role: str
    content: str
    distance: float
    created_at: Optional[str]


class VectorStore:
    """
    Thin wrapper around a single persistent Chroma collection. One vector
    per message, keyed by the SQLite message id so results can always be
    traced back to the row that owns them.
    """

    def __init__(
        self,
        path: str = VECTOR_STORE_PATH,
        collection_name: str = VECTOR_COLLECTION_NAME,
    ) -> None:
        self._client = chromadb.PersistentClient(path=path)
        # Explicit cosine space: without this Chroma defaults to raw L2, which
        # makes SEMANTIC_MAX_DISTANCE mean something different for every embedding
        # dimensionality. Cosine keeps the [0, 2] range predictable and configurable.
        self._collection = self._client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_message(
        self,
        message_id: int,
        conversation_id: int,
        role: str,
        content: str,
        created_at: Optional[str] = None,
    ) -> None:
        """
        Embeds and stores one message. Call this right after MessageRepository.add().
        Silently no-ops for roles outside INDEXABLE_ROLES (e.g. 'system', 'tool') --
        callers don't need to filter before calling this.
        """
        if role not in INDEXABLE_ROLES or not content.strip():
            return
        self._collection.upsert(
            ids=[str(message_id)],
            documents=[content],
            metadatas=[{
                "conversation_id": conversation_id,
                "role": role,
                "created_at": created_at or "",
            }],
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        exclude_conversation_id: Optional[int] = None,
        max_distance: Optional[float] = None,
    ) -> List[RecalledHit]:
        """
        Returns up to top_k messages (any session) most semantically similar
        to `query`, excluding one conversation id (normally the current session,
        since its recent turns are already in context verbatim). If max_distance
        is set, hits with a worse (larger) cosine distance are dropped rather
        than just ranked low -- 'closest of a bad bunch' is not relevant.
        """
        where = None
        if exclude_conversation_id is not None:
            where = {"conversation_id": {"$ne": exclude_conversation_id}}

        results = self._collection.query(query_texts=[query], n_results=top_k, where=where)

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        hits = [
            RecalledHit(
                message_id=int(mid),
                conversation_id=meta.get("conversation_id"),
                role=meta.get("role"),
                content=doc,
                distance=dist,
                created_at=meta.get("created_at") or None,
            )
            for mid, doc, meta, dist in zip(ids, docs, metas, distances)
        ]
        if max_distance is not None:
            hits = [h for h in hits if h["distance"] <= max_distance]
        return hits

    def delete_conversation(self, conversation_id: int) -> None:
        """
        Removes every vector belonging to one conversation. Call this BEFORE
        deleting the conversation from SQLite (see ConversationService.delete_conversation)
        -- if this fails, SQLite still has the conversation and the delete is
        safe to retry; doing it in the other order risks orphaned vectors that
        could resurface a supposedly-deleted conversation's content in recall.
        """
        self._collection.delete(where={"conversation_id": conversation_id})
