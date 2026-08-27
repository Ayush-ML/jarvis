# This Script is responsible for Screen capture and basic screen/cursor info: screenshot,
# resolution, mouse position. See computer_use/__init__.py for the module-wide notes on
# safety (FAILSAFE) and why element-based tools (elements.py) are preferred over raw
# coordinates for clicking -- this file only covers read-only screen state.
from datetime import datetime
from pathlib import Path
from typing import List

import pyautogui

from src.tools.registry import Tool

SCREENSHOT_DIR = "data/screenshots"


def screenshot() -> str:
    Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
    filename = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f") + ".png"
    path = str(Path(SCREENSHOT_DIR) / filename)
    img = pyautogui.screenshot()
    img.save(path)
    return f"Screenshot saved to {path} ({img.width}x{img.height})."


def get_screen_size() -> str:
    width, height = pyautogui.size()
    return f"Screen resolution: {width}x{height}."


def get_mouse_position() -> str:
    x, y = pyautogui.position()
    return f"Mouse is at ({x}, {y})."


TOOLS: List[Tool] = [
    Tool(
        name="screenshot",
        description="Capture the current screen and save it to disk. Returns the file path and resolution. Note: whether the model can actually SEE the saved image depends on the connected model supporting vision -- this tool only captures and saves, it does not attach the image to the conversation.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=screenshot,
    ),
    Tool(
        name="get_screen_size",
        description="Get the screen resolution in pixels.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_screen_size,
    ),
    Tool(
        name="get_mouse_position",
        description="Get the current mouse cursor position.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_mouse_position,
    ),
]
