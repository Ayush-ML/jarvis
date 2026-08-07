# This Script is responsible for Assembling the `messages` list sent to the Model on every turn
# It is the ONLY place that decides what the Model gets to see: the system prompt, the most
# relevant long-term memories, and a bounded window of recent conversation.
#
# OpenAIRequestSchema deliberately does NOT own this -- it stays a stateless description of
# a single request. Call ContextManager.build() fresh each turn and hand its output straight
# to a new OpenAIRequestSchema(messages=...); never accumulate onto one shared schema instance.
from typing import Dict, List
from src.database.repository import MessageRepository
from src.database.models import Message
from src.memory.retriever import MemoryRetriever

SYSTEM_PROMPT = "You are Jarvis, a helpful personal AI assistant."
HISTORY_WINDOW = 12          # recent raw turns considered before budget trimming
APPROX_CHARS_PER_TOKEN = 4   # rough guard so this doesn't need a tokenizer dependency


class ContextManager:
    """
    Builds the messages array for a single turn. Holds no conversation
    state of its own -- everything it needs comes from the database on
    every call, so it can never drift out of sync with what's persisted.
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
        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        memories = self.memory_retriever.retrieve(user_input)
        if memories:
            recalled = "\n".join(f"- {m.content}" for m in memories)
            messages.append({
                "role": "system",
                "content": f"Relevant things you remember about the user:\n{recalled}",
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
