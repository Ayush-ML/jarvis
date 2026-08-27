# No approval gating -- every tool in this package executes immediately, full access within
# the current Windows user, per instruction. This is real, unguarded control of the machine
# the assistant runs on.
#
# Coordinate-based tools (mouse.py, keyboard.py) are FALLBACKS. Prefer elements.py's
# list_interactive_elements/click_element/type_into_element, which target UI elements via
# Windows' UI Automation tree instead of visually estimated pixel coordinates -- most models
# are genuinely unreliable at the latter. See elements.py for details.
from typing import List

from src.tools.registry import Tool
from src.tools.computer_use import screen, mouse, keyboard, windows, elements, launch

TOOLS: List[Tool] = (
    screen.TOOLS
    + mouse.TOOLS
    + keyboard.TOOLS
    + windows.TOOLS
    + elements.TOOLS
    + launch.TOOLS
)

__all__ = ["TOOLS"]
