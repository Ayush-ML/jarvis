# This Script is responsible for Assembling the `messages` list sent to the Model on every turn
# It is the ONLY place that decides what the Model sees, built fresh every turn from exactly
# four sources:
#   1. SOUL.md       -- Jarvis's system prompt / persona (hand-edited Markdown)
#   2. USER.md        -- user profile, injected if it exists yet (read-only for now)
#   3. Session history -- the current conversation's recent turns, verbatim
#   4. Semantic recall -- relevant messages pulled from EVERY other past session
#
# OpenAIRequestSchema stays a stateless request spec -- construct a NEW instance each turn
# with this method's output; never mutate `.messages` on a shared instance across turns.
from typing import Dict, List
from src.database.repository import MessageRepository
from src.database.models import Message
from src.memory.retriever import MemoryRetriever
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
        messages: List[Dict[str, str]] = [{"role": "system", "content": load_soul()}]

        user_profile = load_user_profile()
        if user_profile:
            messages.append({
                "role": "system",
                "content": f"What you know about the user:\n{user_profile}",
            })

        recalled = self.memory_retriever.retrieve(user_input, exclude_conversation_id=conversation_id)
        if recalled:
            block = "\n".join(f"- ({r.role}, past session) {r.content}" for r in recalled)
            messages.append({
                "role": "system",
                "content": f"Relevant context recalled from past sessions:\n{block}",
            })

        history = self.message_repo.recent(conversation_id, HISTORY_WINDOW)
        for msg in self._fit_to_budget(history):
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_input})
        return messages

    def _fit_to_budget(self, history: List[Message]) -> List[Message]:
        """Drop the oldest turns first until the window fits the token budget."""
        budget_chars = self.max_context_tokens * APPROX_CHARS_PER_TOKEN
        kept, used = [], 0
        for msg in reversed(history):
            used += len(msg.content)
            if used > budget_chars:
                break
            kept.append(msg)
        return list(reversed(kept))
