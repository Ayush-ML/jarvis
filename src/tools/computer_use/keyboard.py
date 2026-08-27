# This Script is responsible for Keyboard control: typing text, single key presses, hotkey combos.
# type_text is a FALLBACK -- prefer elements.py's type_into_element, which also guarantees focus
# lands in the intended field rather than relying on a prior click.
from typing import List

import pyautogui

from src.tools.registry import Tool


def type_text(text: str, interval: float = 0.0) -> str:
    pyautogui.write(text, interval=interval)
    return f"Typed: {text!r}"


def press_key(key: str) -> str:
    pyautogui.press(key)
    return f"Pressed key: {key}"


def hotkey(keys: List[str]) -> str:
    if not keys:
        return "Tool error: hotkey requires at least one key."
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey: {'+'.join(keys)}"


TOOLS: List[Tool] = [
    Tool(
        name="type_text",
        description="Type text via simulated keyboard input, into whatever currently has focus. FALLBACK ONLY -- prefer type_into_element, which also guarantees focus lands in the intended field rather than relying on a prior click.",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to type."},
                "interval": {"type": "number", "description": "Seconds between each keystroke. Default 0 (as fast as possible)."},
            },
            "required": ["text"],
        },
        handler=type_text,
    ),
    Tool(
        name="press_key",
        description="Press a single key (e.g. 'enter', 'esc', 'tab', 'f5', 'up').",
        parameters={
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Key name, per pyautogui's key naming (e.g. 'enter', 'esc', 'backspace')."}},
            "required": ["key"],
        },
        handler=press_key,
    ),
    Tool(
        name="hotkey",
        description="Press a combination of keys together (e.g. ['ctrl', 'c'] for copy).",
        parameters={
            "type": "object",
            "properties": {
                "keys": {"type": "array", "items": {"type": "string"}, "description": "Keys to press together, in order (e.g. ['ctrl', 'shift', 'esc'])."},
            },
            "required": ["keys"],
        },
        handler=hotkey,
    ),
]
