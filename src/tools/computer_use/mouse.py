# This Script is responsible for Mouse control: move, click, drag, scroll.
#
# click/drag are FALLBACKS, not the preferred path for clicking UI targets -- see elements.py
# and the module docstring in computer_use/__init__.py for why (visual coordinate estimation
# is a well-known weak point across models; element-based targeting sidesteps it entirely).
#
# KEPT ON PURPOSE: pyautogui.FAILSAFE (default True) aborts any pyautogui call if the mouse is
# physically slammed into a screen corner -- a human's manual kill switch for a runaway action.
# Not disabled here despite "no approvals" -- costs nothing normally, and is the one recovery
# path if a tool call goes somewhere unintended.
from typing import List, Optional, Tuple

import pyautogui

from src.tools.registry import Tool

VALID_BUTTONS = ("left", "right", "middle")


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(value, hi))


def _clamp_to_screen(x: int, y: int) -> Tuple[int, int]:
    width, height = pyautogui.size()
    return _clamp(x, 0, width - 1), _clamp(y, 0, height - 1)


def move_mouse(x: int, y: int, duration: float = 0.1) -> str:
    cx, cy = _clamp_to_screen(x, y)
    pyautogui.moveTo(cx, cy, duration=duration)
    return f"Moved mouse to ({cx}, {cy})."


def click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left", double: bool = False) -> str:
    if button not in VALID_BUTTONS:
        return f"Tool error: button must be one of {VALID_BUTTONS}, got '{button}'."
    if x is not None and y is not None:
        cx, cy = _clamp_to_screen(x, y)
        pyautogui.moveTo(cx, cy)
    else:
        cx, cy = pyautogui.position()
    clicks = 2 if double else 1
    pyautogui.click(x=cx, y=cy, clicks=clicks, button=button)
    kind = "Double-clicked" if double else "Clicked"
    return f"{kind} {button} button at ({cx}, {cy})."


def drag_mouse(start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left", duration: float = 0.3) -> str:
    if button not in VALID_BUTTONS:
        return f"Tool error: button must be one of {VALID_BUTTONS}, got '{button}'."
    sx, sy = _clamp_to_screen(start_x, start_y)
    ex, ey = _clamp_to_screen(end_x, end_y)
    pyautogui.moveTo(sx, sy)
    pyautogui.dragTo(ex, ey, duration=duration, button=button)
    return f"Dragged from ({sx}, {sy}) to ({ex}, {ey}) with {button} button."


def scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> str:
    if x is not None and y is not None:
        cx, cy = _clamp_to_screen(x, y)
        pyautogui.scroll(amount, x=cx, y=cy)
    else:
        pyautogui.scroll(amount)
    direction = "up" if amount > 0 else "down"
    return f"Scrolled {direction} by {abs(amount)}."


TOOLS: List[Tool] = [
    Tool(
        name="move_mouse",
        description="Move the mouse cursor to an absolute screen position.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Target X coordinate in pixels."},
                "y": {"type": "integer", "description": "Target Y coordinate in pixels."},
                "duration": {"type": "number", "description": "Seconds the movement should take (0 = instant). Default 0.1."},
            },
            "required": ["x", "y"],
        },
        handler=move_mouse,
    ),
    Tool(
        name="click",
        description="Click the mouse at a raw pixel coordinate. FALLBACK ONLY -- prefer click_element with a label from list_interactive_elements when the window supports it; estimating coordinates from a screenshot is unreliable. If x/y are omitted, clicks at the current cursor position.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate to click at. Omit to use the current position."},
                "y": {"type": "integer", "description": "Y coordinate to click at. Omit to use the current position."},
                "button": {"type": "string", "enum": list(VALID_BUTTONS), "description": "Which mouse button. Default 'left'."},
                "double": {"type": "boolean", "description": "Double-click instead of single-click. Default false."},
            },
            "required": [],
        },
        handler=click,
    ),
    Tool(
        name="drag_mouse",
        description="Click and drag the mouse from one point to another.",
        parameters={
            "type": "object",
            "properties": {
                "start_x": {"type": "integer"},
                "start_y": {"type": "integer"},
                "end_x": {"type": "integer"},
                "end_y": {"type": "integer"},
                "button": {"type": "string", "enum": list(VALID_BUTTONS), "description": "Default 'left'."},
                "duration": {"type": "number", "description": "Seconds the drag should take. Default 0.3."},
            },
            "required": ["start_x", "start_y", "end_x", "end_y"],
        },
        handler=drag_mouse,
    ),
    Tool(
        name="scroll",
        description="Scroll the mouse wheel. Positive amount scrolls up, negative scrolls down.",
        parameters={
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Scroll amount; sign indicates direction."},
                "x": {"type": "integer", "description": "X position to scroll at. Omit to use the current cursor position."},
                "y": {"type": "integer", "description": "Y position to scroll at. Omit to use the current cursor position."},
            },
            "required": ["amount"],
        },
        handler=scroll,
    ),
]
