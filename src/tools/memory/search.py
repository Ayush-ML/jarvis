# This Script is responsible for explicit, model-directed semantic search over past conversation
# history -- distinct from ContextManager's AUTOMATIC per-turn recall, which searches using the
# raw current user input as the query, every single turn, regardless of whether it's needed. This
# tool exists for when the model needs to look something up with a deliberately refined query
# mid-reasoning. There's inherent overlap with automatic recall -- this isn't a replacement for
# it, it's a way to search more precisely than "whatever the user just said" allows.
#
# Deliberately does NOT exclude the current conversation from results, unlike ContextManager's
# own retrieval (which excludes it since recent turns are already in context verbatim). Doing
# that here would require conversation_id to flow from wherever tool dispatch happens down into
# this handler -- which isn't wired up yet (no dispatch loop exists in this codebase yet). Worst
# case of not excluding it: an occasional redundant result already visible in context, not a
# correctness bug -- a reasonable simplification, not an oversight.
from typing import List

from src.tools.registry import Tool
from src.memory.retriever import MemoryRetriever
from src.memory.vector_store import VectorStore

# Constructed once, module-level -- VectorStore wraps a persistent Chroma client, same
# "expensive resource, build once" reasoning as Transcriber/BrowserSession.
_retriever = MemoryRetriever(VectorStore())


def search_memory(query: str) -> str:
    if not query.strip():
        return "Tool error: query is empty."
    results = _retriever.retrieve(query)
    if not results:
        return "No relevant past conversation found."
    lines = [f"- ({r.role}, past session) {r.content}" for r in results]
    return "Relevant past conversation:\n" + "\n".join(lines)


TOOLS: List[Tool] = [
    Tool(
        name="search_memory",
        description="Search past conversations (any session) for something specific, using a deliberately chosen query. Complements automatic recall -- use this when you need to look up something that isn't directly implied by the user's current message.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for."}},
            "required": ["query"],
        },
        handler=search_memory,
    ),
]
