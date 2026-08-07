# This Script is responsible for the local Vector Store used for Semantic Search across ALL sessions
# Backed by ChromaDB running fully locally: persisted to disk, embedded on-device via Chroma's
# bundled ONNX MiniLM model. No network call, no API key, no dependency on the chat provider --
# swap `_embedding_fn` for a different sentence-transformers/FAISS setup later if you want to,
# nothing outside this file needs to know how the vector search works internally.
import chromadb
from typing import List, Optional, TypedDict
from src.core.config import VECTOR_STORE_PATH, VECTOR_COLLECTION_NAME


class RecalledHit(TypedDict):
    message_id: int
    conversation_id: int
    role: str
    content: str
    distance: float


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
        self._collection = self._client.get_or_create_collection(collection_name)

    def index_message(self, message_id: int, conversation_id: int, role: str, content: str) -> None:
        """Embeds and stores one message. Call this right after MessageRepository.add()."""
        if not content.strip():
            return
        self._collection.upsert(
            ids=[str(message_id)],
            documents=[content],
            metadatas=[{"conversation_id": conversation_id, "role": role}],
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        exclude_conversation_id: Optional[int] = None,
    ) -> List[RecalledHit]:
        """
        Returns the top_k messages (any session) most semantically similar
        to `query`. Excludes one conversation id -- normally the current
        session, since its recent turns are already in context verbatim.
        """
        where = None
        if exclude_conversation_id is not None:
            where = {"conversation_id": {"$ne": exclude_conversation_id}}

        results = self._collection.query(query_texts=[query], n_results=top_k, where=where)

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            RecalledHit(
                message_id=int(mid),
                conversation_id=meta.get("conversation_id"),
                role=meta.get("role"),
                content=doc,
                distance=dist,
            )
            for mid, doc, meta, dist in zip(ids, docs, metas, distances)
        ]
