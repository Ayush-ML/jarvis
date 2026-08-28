# This Script is responsible for reading page content (text, screenshot) and page-level input
# that isn't tied to a specific element: scrolling and key presses (e.g. pressing Enter to
# submit a focused form).
from datetime import datetime
from pathlib import Path
from typing import List

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession

SCREENSHOT_DIR = "data/screenshots"  # same directory computer_use/screen.py uses; kept as its own local constant here deliberately, not a shared import, to avoid coupling unrelated tool categories


def get_page_text(session: BrowserSession = default_session) -> str:
    try:
        text = session.page.inner_text("body")
    except Exception as e:
        return f"Tool error reading page text: {e}"
    text = text.strip()
    if not text:
        return "Page has no visible text content."
    return text


def screenshot(session: BrowserSession = default_session) -> str:
    Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
    filename = "browser_" + datetime.now().strftime("%Y-%m-%d_%H%M%S_%f") + ".png"
    path = str(Path(SCREENSHOT_DIR) / filename)
    try:
        session.page.screenshot(path=path)
    except Exception as e:
        return f"Tool error taking screenshot: {e}"
    return f"Screenshot saved to {path}. Note: whether the model can actually SEE it depends on the connected model supporting vision -- this tool only captures and saves."


def scroll(direction: str = "down", amount: int = 500, session: BrowserSession = default_session) -> str:
    if direction not in ("up", "down"):
        return f"Tool error: direction must be 'up' or 'down', got '{direction}'."
    delta = amount if direction == "down" else -amount
    try:
        session.page.mouse.wheel(0, delta)
    except Exception as e:
        return f"Tool error scrolling: {e}"
    return f"Scrolled {direction} by {amount}px."


def press_key(key: str, session: BrowserSession = default_session) -> str:
    try:
        session.page.keyboard.press(key)
    except Exception as e:
        return f"Tool error pressing key '{key}': {e}"
    return f"Pressed key: {key}"


TOOLS: List[Tool] = [
    Tool(
        name="get_page_text",
        description="Get the visible text content of the current page -- how a JARVIS reading the page would summarize what's on it.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_page_text,
    ),
    Tool(
        name="browser_screenshot",
        description="Capture a screenshot of the current page and save it to disk. Returns the file path. Note: whether the model can actually SEE the saved image depends on the connected model supporting vision.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=screenshot,
    ),
    Tool(
        name="browser_scroll",
        description="Scroll the current page up or down.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down"], "description": "Default 'down'."},
                "amount": {"type": "integer", "description": "Pixels to scroll. Default 500."},
            },
            "required": [],
        },
        handler=scroll,
    ),
    Tool(
        name="browser_press_key",
        description="Press a key on the page (e.g. 'Enter' to submit a focused form, 'Escape' to close a dialog). Acts on whatever currently has focus -- click or type into a field first if a specific element needs to be focused.",
        parameters={
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Key name, e.g. 'Enter', 'Escape', 'Tab'."}},
            "required": ["key"],
        },
        handler=press_key,
    ),
]
