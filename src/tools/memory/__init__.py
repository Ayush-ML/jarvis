# No approval gating -- consistent with computer_use/browser_use.
#
# profile_tools.py: reads/writes USER.md, the always-injected durable user profile.
# search.py: explicit, model-directed semantic search over past conversation history.
from typing import List

from src.tools.registry import Tool
from src.tools.memory import profile_tools, search

TOOLS: List[Tool] = profile_tools.TOOLS + search.TOOLS

__all__ = ["TOOLS"]
