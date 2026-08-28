# No approval gating -- every tool in this package executes immediately, same policy as
# computer_use. Real, unguarded browser control.
#
# Element-based tools (elements.py) are the preferred way to click/type on a page, over raw
# coordinates -- the same "structural targeting beats visual estimation" reasoning as
# computer_use/elements.py, with the added benefit that DOM structure is unaffected by layout,
# scroll position, or zoom (all of which shift where something visually IS on a webpage).
#
# A few tool names are prefixed with "browser_" (browser_screenshot, browser_scroll,
# browser_press_key) specifically to avoid colliding with computer_use's identically-named
# desktop tools once both categories are registered into the same ToolRegistry.
from typing import List

from src.tools.registry import Tool
from src.tools.browser_use import navigation, content, elements, tabs

TOOLS: List[Tool] = (
    navigation.TOOLS
    + content.TOOLS
    + elements.TOOLS
    + tabs.TOOLS
)

__all__ = ["TOOLS"]
