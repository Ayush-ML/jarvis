# This Script is responsible for explicit, deliberate memory tools backed by USER.md -- the
# durable, always-injected user-profile file (see src/memory/profile.py,
# src/brain/context_manager.py). Distinct from search.py's search_memory, which searches raw
# conversation history semantically -- these tools write to (and read back) the structured
# profile that's included in EVERY turn's context unconditionally, not just when a semantic
# search happens to surface it.
from typing import List

from src.tools.registry import Tool
from src.memory.profile import remember_user_fact, forget_user_fact, get_user_profile_text

TOOLS: List[Tool] = [
    Tool(
        name="remember_fact",
        description="Remember a durable fact about the user (a preference, a detail about their life, how they like things done). Stored in the user profile, which is included in every future conversation automatically -- use this for things worth recalling long-term, not passing details specific to the current task.",
        parameters={
            "type": "object",
            "properties": {"fact": {"type": "string", "description": "The fact to remember, stated plainly (e.g. 'prefers window seats when flying')."}},
            "required": ["fact"],
        },
        handler=remember_user_fact,
    ),
    Tool(
        name="forget_fact",
        description="Remove a previously remembered fact about the user, matched by a substring of its text. Fails cleanly (asks for a more specific substring) if more than one remembered fact matches.",
        parameters={
            "type": "object",
            "properties": {"fact_substring": {"type": "string", "description": "A substring uniquely identifying the fact to remove."}},
            "required": ["fact_substring"],
        },
        handler=forget_user_fact,
    ),
    Tool(
        name="get_user_profile",
        description="Get everything currently remembered about the user. Useful to check before remembering something new (avoid near-duplicates), or when directly asked what you know about the user.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_user_profile_text,
    ),
]
