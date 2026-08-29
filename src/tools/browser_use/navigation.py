# This Script is responsible for Page navigation: go to a URL, back/forward/reload, current URL.
#
# wait_until defaults to "networkidle" (not Playwright's own default of "load") -- "load" alone
# leaves many JS-heavy/SPA pages with content that hasn't finished hydrating yet, which
# get_page_text/list_interactive_elements called right after would see incompletely. "networkidle"
# isn't perfect either (Playwright's own docs caution against it for pages with persistent
# background connections -- analytics, websockets -- which may never go idle) -- it's a pragmatic
# default for arbitrary/unknown pages, overridable per-call for sites where it's the wrong choice.
from typing import List

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession
from src.core.config import BROWSER_NAVIGATION_TIMEOUT_MS

WAIT_UNTIL_OPTIONS = ("load", "domcontentloaded", "networkidle", "commit")
DEFAULT_WAIT_UNTIL = "networkidle"


def navigate(url: str, wait_until: str = DEFAULT_WAIT_UNTIL, session: BrowserSession = default_session) -> str:
    if wait_until not in WAIT_UNTIL_OPTIONS:
        return f"Tool error: wait_until must be one of {WAIT_UNTIL_OPTIONS}, got '{wait_until}'."
    try:
        session.page.goto(url, wait_until=wait_until, timeout=BROWSER_NAVIGATION_TIMEOUT_MS)
    except Exception as e:
        return f"Tool error navigating to '{url}': {e}"
    return f"Navigated to {session.page.url}"


def go_back(wait_until: str = DEFAULT_WAIT_UNTIL, session: BrowserSession = default_session) -> str:
    if wait_until not in WAIT_UNTIL_OPTIONS:
        return f"Tool error: wait_until must be one of {WAIT_UNTIL_OPTIONS}, got '{wait_until}'."
    try:
        session.page.go_back(wait_until=wait_until, timeout=BROWSER_NAVIGATION_TIMEOUT_MS)
    except Exception as e:
        return f"Tool error going back: {e}"
    return f"Went back. Now at {session.page.url}"


def go_forward(wait_until: str = DEFAULT_WAIT_UNTIL, session: BrowserSession = default_session) -> str:
    if wait_until not in WAIT_UNTIL_OPTIONS:
        return f"Tool error: wait_until must be one of {WAIT_UNTIL_OPTIONS}, got '{wait_until}'."
    try:
        session.page.go_forward(wait_until=wait_until, timeout=BROWSER_NAVIGATION_TIMEOUT_MS)
    except Exception as e:
        return f"Tool error going forward: {e}"
    return f"Went forward. Now at {session.page.url}"


def reload_page(wait_until: str = DEFAULT_WAIT_UNTIL, session: BrowserSession = default_session) -> str:
    if wait_until not in WAIT_UNTIL_OPTIONS:
        return f"Tool error: wait_until must be one of {WAIT_UNTIL_OPTIONS}, got '{wait_until}'."
    try:
        session.page.reload(wait_until=wait_until, timeout=BROWSER_NAVIGATION_TIMEOUT_MS)
    except Exception as e:
        return f"Tool error reloading: {e}"
    return f"Reloaded {session.page.url}"


def get_current_url(session: BrowserSession = default_session) -> str:
    return f"Current URL: {session.page.url}"


_WAIT_UNTIL_PARAM = {"type": "string", "enum": list(WAIT_UNTIL_OPTIONS), "description": f"When to consider the navigation finished. Default '{DEFAULT_WAIT_UNTIL}'; use 'load' for pages with persistent background connections (websockets, analytics) that may never go network-idle."}

TOOLS: List[Tool] = [
    Tool(
        name="navigate",
        description="Navigate the active browser tab to a URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to load."},
                "wait_until": _WAIT_UNTIL_PARAM,
            },
            "required": ["url"],
        },
        handler=navigate,
    ),
    Tool(
        name="go_back",
        description="Go back to the previous page in the active tab's history.",
        parameters={"type": "object", "properties": {"wait_until": _WAIT_UNTIL_PARAM}, "required": []},
        handler=go_back,
    ),
    Tool(
        name="go_forward",
        description="Go forward in the active tab's history.",
        parameters={"type": "object", "properties": {"wait_until": _WAIT_UNTIL_PARAM}, "required": []},
        handler=go_forward,
    ),
    Tool(
        name="reload_page",
        description="Reload the active tab's current page.",
        parameters={"type": "object", "properties": {"wait_until": _WAIT_UNTIL_PARAM}, "required": []},
        handler=reload_page,
    ),
    Tool(
        name="get_current_url",
        description="Get the URL currently loaded in the active tab.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=get_current_url,
    ),
]
