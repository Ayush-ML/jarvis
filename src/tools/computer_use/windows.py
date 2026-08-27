# This Script is responsible for Window management: enumerate, focus, resize, move, and change
# the state (minimize/maximize/restore/close) of open windows, matched by (partial) title.
#
# WINDOWS PLATFORM NOTE: Window.activate() can silently fail due to Windows' own foreground-lock
# restriction (a background process generally can't force itself to the foreground unless the OS
# grants it permission) -- that's an OS-level limitation, not a bug in this code, if it comes up.
from typing import Any, List, Optional

import pygetwindow as gw

from src.tools.registry import Tool

VALID_WINDOW_STATES = ("minimize", "maximize", "restore", "close")


def _find_window(title: str) -> Optional[Any]:
    """Returns the first open window (a pygetwindow Window object) whose title contains `title`, or None."""
    matches = gw.getWindowsWithTitle(title)
    return matches[0] if matches else None


def list_windows() -> str:
    titles = [t for t in gw.getAllTitles() if t.strip()]
    if not titles:
        return "No open windows found."
    return "Open windows:\n" + "\n".join(f"- {t}" for t in titles)


def get_active_window() -> str:
    win = gw.getActiveWindow()
    if win is None:
        return "No window is currently active/focused."
    return f"Active window: '{win.title}' at ({win.left}, {win.top}), size {win.width}x{win.height}."


def activate_window(title: str) -> str:
    win = _find_window(title)
    if win is None:
        return f"Tool error: no open window matching '{title}'."
    try:
        win.activate()
    except Exception as e:
        return f"Tool error: could not activate '{win.title}' ({e}). Windows sometimes blocks background processes from taking focus."
    return f"Activated window: '{win.title}'."


def set_window_state(title: str, state: str) -> str:
    if state not in VALID_WINDOW_STATES:
        return f"Tool error: state must be one of {VALID_WINDOW_STATES}, got '{state}'."
    win = _find_window(title)
    if win is None:
        return f"Tool error: no open window matching '{title}'."
    getattr(win, state)()
    return f"Set window '{win.title}' to state: {state}."


def resize_window(title: str, width: int, height: int) -> str:
    win = _find_window(title)
    if win is None:
        return f"Tool error: no open window matching '{title}'."
    win.resizeTo(width, height)
    return f"Resized window '{win.title}' to {width}x{height}."


def move_window(title: str, x: int, y: int) -> str:
    win = _find_window(title)
    if win is None:
        return f"Tool error: no open window matching '{title}'."
    win.moveTo(x, y)
    return f"Moved window '{win.title}' to ({x}, {y})."


TOOLS: List[Tool] = [
    Tool(
        name="list_windows",
        description="List the titles of all open windows.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=list_windows,
    ),
    Tool(
        name="get_active_window",
        description="Get the title and position of the currently focused window.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_active_window,
    ),
    Tool(
        name="activate_window",
        description="Bring a window to the foreground and give it focus, matched by (partial) title.",
        parameters={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Full or partial window title to match."}},
            "required": ["title"],
        },
        handler=activate_window,
    ),
    Tool(
        name="set_window_state",
        description="Minimize, maximize, restore, or close a window, matched by (partial) title.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Full or partial window title to match."},
                "state": {"type": "string", "enum": list(VALID_WINDOW_STATES)},
            },
            "required": ["title", "state"],
        },
        handler=set_window_state,
    ),
    Tool(
        name="resize_window",
        description="Resize a window, matched by (partial) title.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
            },
            "required": ["title", "width", "height"],
        },
        handler=resize_window,
    ),
    Tool(
        name="move_window",
        description="Move a window to a new screen position, matched by (partial) title.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["title", "x", "y"],
        },
        handler=move_window,
    ),
]
