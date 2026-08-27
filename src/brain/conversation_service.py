# This Script is responsible for Writing a Message to BOTH SQLite and the Vector Store as one unit,
# and for the two other operations that must touch both stores together: rolling summarization
# and conversation deletion. SQLite is always the source of truth and always succeeds or the whole
# call raises. Vector indexing is best-effort immediately after: if it fails (Chroma down, embedding
# error, etc.) the message is left with indexed=0 and picked up later by backfill() -- so a
# transient failure here never loses conversation history, it just delays that message's searchability.
import logging
from typing import Optional
from src.database.repository import MessageRepository, ConversationRepository
from src.database.models import Message
from src.memory.vector_store import VectorStore
from src.brain.summarizer import Summarizer
from src.core.config import HISTORY_WINDOW, SUMMARY_BATCH_SIZE
from src.core.message_types import TextContent

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Single entry point for persisting a turn. Nothing else in the codebase
    should call MessageRepository.add() and VectorStore.index_message()
    separately -- doing so is exactly how the two stores drift apart.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        conversation_repo: ConversationRepository,
        vector_store: VectorStore,
        summarizer: Optional[Summarizer] = None,
    ) -> None:
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo
        self.vector_store = vector_store
        self.summarizer = summarizer  # None disables rolling summarization entirely

    def add_message(self, conversation_id: int, role: str, content: TextContent) -> Message:
        message = self.message_repo.add(conversation_id, role, content)
        self._try_index(message)
        self._maybe_summarize(conversation_id)
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

    def delete_conversation(self, conversation_id: int) -> None:
        """
        Deletes a conversation and everything derived from it. Vector entries
        are removed BEFORE the SQLite row: if the vector delete fails and this
        raises, the conversation still exists in SQLite (safe to retry) -- the
        opposite order risks orphaned vectors that could resurface a
        supposedly-deleted conversation's content in future semantic recall.
        """
        self.vector_store.delete_conversation(conversation_id)
        self.conversation_repo.delete(conversation_id)

    def _try_index(self, message: Message) -> bool:
        if message.id is None:
            logger.warning("Cannot index message without an ID")
            return False

        try:
            self.vector_store.index_message(
                message.id,
                message.conversation_id,
                message.role,
                message.content["text"],
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

    def _maybe_summarize(self, conversation_id: int) -> None:
        if self.summarizer is None:
            return

        # Cheap short-circuit: only do the full scan below once there's even
        # a theoretical chance a full batch has fallen outside the window.
        total = self.message_repo.count(conversation_id)
        if total < HISTORY_WINDOW + SUMMARY_BATCH_SIZE:
            return

        conversation = self.conversation_repo.get(conversation_id)
        if conversation is None:
            return

        all_messages = self.message_repo.all_for_conversation(conversation_id)
        recent_ids = {m.id for m in all_messages[-HISTORY_WINDOW:]}
        pending = [
            m for m in all_messages
            if (
                m.id is not None
                and m.id > conversation.summarized_through_message_id
                and m.id not in recent_ids
            )
        ]
        if len(pending) < SUMMARY_BATCH_SIZE:
            return

        last_pending_message = pending[-1]
        if last_pending_message.id is None:
            return

        try:
            new_summary = self.summarizer.summarize(conversation.summary, pending)
            self.conversation_repo.update_summary(
                conversation_id,
                new_summary,
                last_pending_message.id,
            )
        except Exception:
            # Same philosophy as indexing failures: a summarization hiccup must
            # never block the turn. Worst case, this batch gets retried once
            # the NEXT batch also becomes pending (summarized_through_message_id
            # didn't advance, so `pending` next time is a superset of this one).
            logger.warning("Failed to summarize conversation %s", conversation_id, exc_info=True)
