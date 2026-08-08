# This Script is responsible for Assembling the `messages` list sent to the Model on every turn
# It is the ONLY place that decides what the Model sees, built fresh every turn from exactly
# four sources, in priority order (highest first):
#   1. SOUL.md        -- Jarvis's system prompt / persona (mandatory, hand-edited Markdown)
#   2. User's input     -- the current turn (mandatory)
#   3. Session history -- the current conversation's recent turns, verbatim
#   4. USER.md          -- user profile, injected if it exists yet (read-only for now)
#   5. Semantic recall  -- relevant messages pulled from EVERY other past session
#
# The token budget covers the WHOLE assembled list, not just history -- SOUL.md, the
# profile block and the recall block all count against it too. When over budget, the
# lowest-priority pieces above are trimmed first: recall entries, then oldest history,
# then the profile block. SOUL.md and the current input are never trimmed.
#
# OpenAIRequestSchema stays a stateless request spec -- construct a NEW instance each turn
# with this method's output; never mutate `.messages` on a shared instance across turns.
from typing import Dict, List
from src.database.repository import MessageRepository
from src.database.models import Message
from src.memory.retriever import MemoryRetriever, RecalledMessage
from src.memory.profile import load_soul, load_user_profile

HISTORY_WINDOW = 12          # recent raw turns considered before budget trimming
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
        memory_retriever: MemoryRetriever,
        max_context_tokens: int = 6000,
    ) -> None:
        self.message_repo = message_repo
        self.memory_retriever = memory_retriever
        self.max_context_tokens = max_context_tokens

    def build(self, conversation_id: int, user_input: str) -> List[Dict[str, str]]:
        soul = load_soul()
        user_profile = load_user_profile()
        recalled = self.memory_retriever.retrieve(user_input, exclude_conversation_id=conversation_id)
        history = self.message_repo.recent(conversation_id, HISTORY_WINDOW)

        budget_chars = self.max_context_tokens * APPROX_CHARS_PER_TOKEN
        remaining = budget_chars - len(soul) - len(user_input)

        history, remaining = self._fit_history(history, remaining)
        recalled, remaining = self._fit_recalled(recalled, remaining)
        if user_profile and len(user_profile) > remaining:
            user_profile = None  # profile is lowest priority -- drop it whole rather than truncate mid-sentence

        messages: List[Dict[str, str]] = [{"role": "system", "content": soul}]

        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})

        if recalled:
            block = "\n".join(f"- ({r.role}, past session) {r.content}" for r in recalled)
            messages.append({
                "role": "system",
                "content": f"Relevant context recalled from past sessions:\n{block}",
            })

        if user_profile:
            messages.append({
                "role": "system",
                "content": f"What you know about the user:\n{user_profile}",
            })

        messages.append({"role": "user", "content": user_input})
        return messages

    @staticmethod
    def _fit_history(history: List[Message], remaining: int) -> tuple[List[Message], int]:
        """Keeps as many of the most recent turns as fit, dropping oldest first."""
        kept, used = [], 0
        for msg in reversed(history):
            cost = len(msg.content)
            if used + cost > remaining:
                break
            used += cost
            kept.append(msg)
        return list(reversed(kept)), remaining - used

    @staticmethod
    def _fit_recalled(recalled: List[RecalledMessage], remaining: int) -> tuple[List[RecalledMessage], int]:
        """Keeps the most relevant recall hits first (list is already similarity-ranked), drops the rest."""
        kept, used = [], 0
        for msg in recalled:
            cost = len(msg.content)
            if used + cost > remaining:
                break
            used += cost
            kept.append(msg)
        return kept, remaining - used
