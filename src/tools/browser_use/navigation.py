# This Script is responsible for Page navigation: go to a URL, back/forward/reload, current URL.
from typing import List

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession


def navigate(url: str, session: BrowserSession = default_session) -> str:
    try:
        session.page.goto(url)
    except Exception as e:
        return f"Tool error navigating to '{url}': {e}"
    return f"Navigated to {session.page.url}"


def go_back(session: BrowserSession = default_session) -> str:
    try:
        session.page.go_back()
    except Exception as e:
        return f"Tool error going back: {e}"
    return f"Went back. Now at {session.page.url}"


def go_forward(session: BrowserSession = default_session) -> str:
    try:
        session.page.go_forward()
    except Exception as e:
        return f"Tool error going forward: {e}"
    return f"Went forward. Now at {session.page.url}"


def reload_page(session: BrowserSession = default_session) -> str:
    try:
        session.page.reload()
    except Exception as e:
        return f"Tool error reloading: {e}"
    return f"Reloaded {session.page.url}"


def get_current_url(session: BrowserSession = default_session) -> str:
    return f"Current URL: {session.page.url}"


TOOLS: List[Tool] = [
    Tool(
        name="navigate",
        description="Navigate the active browser tab to a URL.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL to load."}},
            "required": ["url"],
        },
        handler=navigate,
    ),
    Tool(
        name="go_back",
        description="Go back to the previous page in the active tab's history.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=go_back,
    ),
    Tool(
        name="go_forward",
        description="Go forward in the active tab's history.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=go_forward,
    ),
    Tool(
        name="reload_page",
        description="Reload the active tab's current page.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=reload_page,
    ),
    Tool(
        name="get_current_url",
        description="Get the URL currently loaded in the active tab.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_current_url,
    ),
]
