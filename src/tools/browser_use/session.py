# This Script is responsible for owning the Playwright browser lifecycle -- one long-lived
# browser + a single shared BrowserContext + a list of pages (tabs) within it, started lazily
# on first use and kept alive across every tool call in this category. Same reasoning as
# Transcriber/MCPRegistry: browser startup is expensive, and tools need to act on the SAME page
# a previous tool call left them on.
#
# ALL tabs share ONE BrowserContext (created explicitly via browser.new_context(), pages opened
# via context.new_page()) -- NOT browser.new_page() directly, which creates a NEW ISOLATED
# context per call (separate cookies/storage per "tab"). That would silently defeat the whole
# point of staying logged into your accounts across tabs.
#
# NEW TABS ARE AUTO-TRACKED: context.on("page", ...) fires for pages that appear as a side
# effect of page actions too (a target="_blank" link, window.open()) -- not just ones opened
# explicitly via new_tab(). Without this, clicking such a link would open a real new tab that
# session.pages simply doesn't know about, leaving the active tab stuck on the old page.
#
# JS DIALOGS (alert/confirm/prompt) ARE AUTO-DISMISSED by default -- Playwright leaves these
# unhandled otherwise, which can stall a page indefinitely. Dismiss (not accept) is the safer
# default: auto-accepting a "are you sure you want to delete this?" confirm would be worse than
# auto-declining it. Every page (initial and auto-detected) gets this handler.
#
# Uses playwright.sync_api specifically (not the async API) so this fits ToolRegistry's fully
# synchronous call_tool(name, arguments) -> str contract directly, no async/sync bridging needed.
import logging
from typing import List, Optional

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

from src.core.config import BROWSER_HEADLESS

logger = logging.getLogger(__name__)


class BrowserSession:
    """
    Lazily-started, long-lived browser session. Not thread-safe -- Playwright's
    sync API is meant to be driven from a single thread; if tool calls can
    arrive from multiple threads later, that needs its own serialization,
    not something this class does today.
    """

    def __init__(self, headless: bool = BROWSER_HEADLESS) -> None:
        self._headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._pages: List[Page] = []
        self._active_index = 0

    def _ensure_started(self) -> None:
        if self._browser is not None:
            return
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context()
        self._context.on("page", self._on_new_page)
        self._pages = []
        first_page = self._context.new_page()
        # Explicit call here (not relying solely on the "page" event) covers the case where that
        # event doesn't fire for a page we created ourselves via context.new_page() -- _on_new_page
        # is idempotent (checks membership before appending), so this is safe even if it also fires.
        self._on_new_page(first_page)

    def _on_new_page(self, page: Page) -> None:
        if page not in self._pages:
            self._pages.append(page)
            page.on("dialog", self._on_dialog)
            logger.info("New tab opened: %s", page.url or "(blank)")
        self._active_index = self._pages.index(page)  # a new tab becomes active, matching normal browser UX

    def _on_dialog(self, dialog) -> None:
        logger.info("Auto-dismissing browser dialog (%s): %s", dialog.type, dialog.message)
        dialog.dismiss()

    @property
    def page(self) -> Page:
        """The currently active tab. Starts the browser on first access."""
        self._ensure_started()
        return self._pages[self._active_index]

    @property
    def pages(self) -> List[Page]:
        self._ensure_started()
        return self._pages

    @property
    def active_index(self) -> int:
        return self._active_index

    def new_tab(self, url: Optional[str] = None) -> int:
        self._ensure_started()
        page = self._context.new_page()
        self._on_new_page(page)
        if url:
            page.goto(url)
        return self._active_index

    def switch_tab(self, index: int) -> None:
        self._ensure_started()
        if not (0 <= index < len(self._pages)):
            raise IndexError(f"no tab at index {index} ({len(self._pages)} tab(s) open)")
        self._active_index = index

    def close_tab(self, index: Optional[int] = None) -> None:
        self._ensure_started()
        idx = self._active_index if index is None else index
        if not (0 <= idx < len(self._pages)):
            raise IndexError(f"no tab at index {idx} ({len(self._pages)} tab(s) open)")
        self._pages[idx].close()
        del self._pages[idx]
        if not self._pages:
            self._on_new_page(self._context.new_page())  # never leave zero tabs open
        else:
            self._active_index = min(self._active_index, len(self._pages) - 1)

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._context = None
        self._playwright = None
        self._pages = []
        self._active_index = 0


# Shared across every browser_use tool -- same reasoning as playback_reference.default_playback_reference:
# every tool call site needs to be talking about the same live browser, not a fresh one each time.
default_session = BrowserSession()
