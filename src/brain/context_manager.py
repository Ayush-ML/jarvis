# This Script is responsible for Assembling the `messages` list sent to the Model on every turn
# It is the ONLY place that decides what the Model sees, built fresh every turn from exactly
# five sources, in priority order (highest first, i.e. dropped last when over budget):
#   1. SOUL.md         -- Jarvis's system prompt / persona (mandatory, hand-edited Markdown)
#   2. User's input      -- the current turn (mandatory)
#   3. Session history  -- the current conversation's recent turns, verbatim
#   4. Rolling summary  -- condensed record of this SAME conversation's turns that have
#                          already fallen out of the history window (see ConversationService
#                          / Summarizer) -- without this, a long single session just silently
#                          loses its early turns once HISTORY_WINDOW is exceeded
#   5. Semantic recall  -- relevant messages pulled from EVERY other past session
#   6. USER.md           -- user profile, injected if it exists yet (read-only for now)
#
# The token budget covers the WHOLE assembled list, not just history -- SOUL.md, the summary,
# the recall block and the profile block all count against it too. When over budget, the
# lowest-priority pieces above are trimmed first: profile, then recall, then the summary,
# then oldest history. SOUL.md and the current input are never trimmed.
#
# OpenAIRequestSchema stays a stateless request spec -- construct a NEW instance each turn
# with this method's output; never mutate `.messages` on a shared instance across turns.
from typing import List, Tuple
from src.database.repository import MessageRepository, ConversationRepository
from src.database.models import Message
from src.memory.retriever import MemoryRetriever, RecalledMessage
from src.memory.profile import load_soul, load_user_profile
from src.core.config import HISTORY_WINDOW
from src.core.message_types import ChatMessage

APPROX_CHARS_PER_TOKEN = 4   # rough guard so this doesn't need a tokenizer dependency


class ContextManager:
    """
    Builds the messages array for a single turn. Holds no conversation
    state of its own -- everything it needs comes from disk (SQLite +
    the vector store + the two Markdown files) on every call, so it can
    never drift out of sync with what's actually persisted.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        conversation_repo: ConversationRepository,
        memory_retriever: MemoryRetriever,
        max_context_tokens: int = 6000,
    ) -> None:
        self.message_repo = message_repo
        self.conversation_repo = conversation_repo
        self.memory_retriever = memory_retriever
        self.max_context_tokens = max_context_tokens

    def build(self, conversation_id: int, user_input: str) -> List[ChatMessage]:
        soul = load_soul()
        user_profile = load_user_profile()
        conversation = self.conversation_repo.get(conversation_id)
        summary = conversation.summary if conversation else None
        recalled = self.memory_retriever.retrieve(user_input, exclude_conversation_id=conversation_id)
        history = self.message_repo.recent(conversation_id, HISTORY_WINDOW)

        budget_chars = self.max_context_tokens * APPROX_CHARS_PER_TOKEN
        remaining = budget_chars - len(soul) - len(user_input)

        history, remaining = self._fit_history(history, remaining)
        summary, remaining = self._fit_block(summary, remaining)
        recalled, remaining = self._fit_recalled(recalled, remaining)
        user_profile, remaining = self._fit_block(user_profile, remaining)

        messages: List[ChatMessage] = [{"role": "system", "content": {"type": "text", "text": soul}}]

        if summary:
            messages.append({
                "role": "system",
                "content": {"type": "text", "text": f"Summary of earlier parts of this conversation:\n{summary}"}
            })

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        if recalled:
            block = "\n".join(f"- ({r.role}, past session) {r.content['text']}" for r in recalled)
            messages.append({
                "role": "system",
                "content": {"type": "text", "text": f"Relevant context recalled from past sessions:\n{block}"},
            })

        if user_profile:
            messages.append({
                "role": "system",
                "content": {"type": "text", "text": f"What you know about the user:\n{user_profile}"},
            })

        messages.append({"role": "user", "content": {"type": "text","text": user_input}})
        return messages

    @staticmethod
    def _fit_history(history: List[Message], remaining: int) -> Tuple[List[Message], int]:
        """Keeps as many of the most recent turns as fit, dropping oldest first."""
        kept, used = [], 0
        for msg in reversed(history):
            cost = len(msg.content["text"])
            if used + cost > remaining:
                break
            used += cost
            kept.append(msg)
        return list(reversed(kept)), remaining - used

    @staticmethod
    def _fit_recalled(recalled: List[RecalledMessage], remaining: int) -> Tuple[List[RecalledMessage], int]:
        """Keeps the most relevant recall hits first (list is already similarity-ranked), drops the rest."""
        kept, used = [], 0
        for msg in recalled:
            cost = len(msg.content["text"])
            if used + cost > remaining:
                break
            used += cost
            kept.append(msg)
        return kept, remaining - used

    @staticmethod
    def _fit_block(text, remaining: int):
        """Shared all-or-nothing fit for a single text block (summary or profile) -- never truncated mid-sentence."""
        if not text:
            return text, remaining
        if len(text) > remaining:
            return None, remaining
        return text, remaining - len(text)
