# This Script is responsible for Writing a Message to BOTH SQLite and the Vector Store as one unit
# SQLite is always the source of truth and always succeeds or the whole call raises. Vector
# indexing is best-effort immediately after: if it fails (Chroma down, embedding error, etc.)
# the message is left with indexed=0 and picked up later by backfill() -- so a transient
# failure here never loses conversation history, it just delays that message's searchability.
import logging
from typing import List, Optional
from src.database.repository import MessageRepository
from src.database.models import Message
from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Single entry point for persisting a turn. Nothing else in the codebase
    should call MessageRepository.add() and VectorStore.index_message()
    separately -- doing so is exactly how the two stores drift apart.
    """

    def __init__(self, message_repo: MessageRepository, vector_store: VectorStore) -> None:
        self.message_repo = message_repo
        self.vector_store = vector_store

    def add_message(self, conversation_id: int, role: str, content: str) -> Message:
        message = self.message_repo.add(conversation_id, role, content)
        self._try_index(message)
        return message

    def backfill(self, limit: int = 200) -> int:
        """
        Catches up any message left with indexed=0 -- either from a past
        indexing failure, or from role-based skips being retried harmlessly.
        Call periodically (e.g. on startup) rather than never; returns the
        number of messages successfully indexed this call.
        """
        pending = self.message_repo.unindexed(limit=limit)
        indexed_count = 0
        for message in pending:
            if self._try_index(message):
                indexed_count += 1
        return indexed_count

    def _try_index(self, message: Message) -> bool:
        try:
            self.vector_store.index_message(
                message.id,
                message.conversation_id,
                message.role,
                message.content,
                created_at=message.created_at,
            )
            self.message_repo.mark_indexed(message.id)
            return True
        except Exception:
            # Deliberately broad: any failure here (network, disk, embedding
            # error) must not lose the message or block the chat turn -- it
            # just stays indexed=0 and backfill() retries it later.
            logger.warning("Failed to index message %s into the vector store", message.id, exc_info=True)
            return False
