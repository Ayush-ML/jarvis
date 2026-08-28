# This Script is responsible for Tab (multi-page) management within the browser session.
from typing import List, Optional

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession


def list_tabs(session: BrowserSession = default_session) -> str:
    pages = session.pages
    lines = []
    for i, page in enumerate(pages):
        marker = "*" if i == session.active_index else " "
        lines.append(f"{marker} [{i}] {page.url}")
    return "Open tabs (* = active):\n" + "\n".join(lines)


def new_tab(url: str = "", session: BrowserSession = default_session) -> str:
    try:
        index = session.new_tab(url or None)
    except Exception as e:
        return f"Tool error opening new tab: {e}"
    return f"Opened new tab [{index}]" + (f" at {url}" if url else " (blank).")


def switch_tab(index: int, session: BrowserSession = default_session) -> str:
    try:
        session.switch_tab(index)
    except Exception as e:
        return f"Tool error switching tab: {e}"
    return f"Switched to tab [{index}]: {session.page.url}"


def close_tab(index: Optional[int] = None, session: BrowserSession = default_session) -> str:
    try:
        session.close_tab(index)
    except Exception as e:
        return f"Tool error closing tab: {e}"
    return f"Closed tab. Active tab is now [{session.active_index}]: {session.page.url}"


TOOLS: List[Tool] = [
    Tool(
        name="list_tabs",
        description="List all open browser tabs and which one is active.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=list_tabs,
    ),
    Tool(
        name="new_tab",
        description="Open a new browser tab, optionally navigating it to a URL. Becomes the active tab.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to load in the new tab. Omit for a blank tab."}},
            "required": [],
        },
        handler=new_tab,
    ),
    Tool(
        name="switch_tab",
        description="Switch which tab is active, by index from list_tabs.",
        parameters={
            "type": "object",
            "properties": {"index": {"type": "integer", "description": "Tab index from list_tabs."}},
            "required": ["index"],
        },
        handler=switch_tab,
    ),
    Tool(
        name="close_tab",
        description="Close a browser tab by index. Omit index to close the currently active tab. A new blank tab opens automatically if this closes the last one.",
        parameters={
            "type": "object",
            "properties": {"index": {"type": "integer", "description": "Tab index from list_tabs. Omit to close the active tab."}},
            "required": [],
        },
        handler=close_tab,
    ),
]
