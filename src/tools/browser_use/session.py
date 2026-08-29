# This Script is responsible for owning the Playwright browser lifecycle -- one long-lived
# browser + a single shared BrowserContext + a list of pages (tabs) within it, started lazily
# on first use and kept alive across every tool call in this category.
#
# ALL tabs share ONE BrowserContext (context.new_page(), not browser.new_page() -- the latter
# creates a NEW ISOLATED context per call, silently defeating shared login state across tabs).
#
# NEW TABS ARE AUTO-TRACKED via context.on("page", ...), catching ones that appear as a side
# effect of page actions (target="_blank" links, window.open()), not just explicit new_tab() calls.
#
# JS DIALOGS are auto-dismissed (not accepted) by default on every page -- the safer failure mode.
#
# DOWNLOADS are auto-saved to DOWNLOAD_DIR and tracked (see content.py's get_recent_downloads).
# accept_downloads=True is passed explicitly at context creation rather than relying on whatever
# the installed Playwright version currently defaults to.
#
# CONTEXT-CHANGE NOTIFICATIONS: add_context_change_listener() lets other modules (specifically
# elements.py's label cache) know whenever the active page's content might have changed out from
# under anything they cached -- covers navigation of the ACTIVE page, tab switches, a new tab
# becoming active, and tab closes. Deliberately a generic pub/sub rather than session.py importing
# elements.py directly (or vice versa) -- keeps the dependency direction one-way.
#
# TIMEOUTS: Playwright's own default action timeout is 30s -- long enough that a single bad
# click_element call on a locator that never resolves would stall this whole (synchronous)
# conversation turn. Set explicitly, shorter, at both context and per-page level (not relying on
# uncertain inheritance behavior between the two).
#
# Uses playwright.sync_api specifically (not the async API) so this fits ToolRegistry's fully
# synchronous call_tool(name, arguments) -> str contract directly, no async/sync bridging needed.
import atexit
import logging
from pathlib import Path
from typing import Callable, List, Optional

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

from src.core.config import BROWSER_HEADLESS, BROWSER_ACTION_TIMEOUT_MS

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "data/downloads"
MAX_TRACKED_DOWNLOADS = 20


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
        self._context_change_listeners: List[Callable[[], None]] = []
        self.recent_downloads: List[str] = []  # most recent last; saved paths, capped at MAX_TRACKED_DOWNLOADS

    def _ensure_started(self) -> None:
        if self._browser is not None:
            return
        self._playwright = sync_playwright().start()
        if self._playwright is None:
            raise RuntimeError("Failed to start Playwright")
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        if self._browser is None:
            raise RuntimeError("Failed to launch Chromium browser")
        self._context = self._browser.new_context(accept_downloads=True)
        if self._context is None:
            raise RuntimeError("Failed to create BrowserContext")
        self._context.set_default_timeout(BROWSER_ACTION_TIMEOUT_MS)
        self._context.on("page", self._on_new_page)
        self._pages = []
        first_page = self._context.new_page()
        if first_page is None:
            raise RuntimeError("Failed to create first page in BrowserContext")
        # Explicit call here (not relying solely on the "page" event) covers the case where that
        # event doesn't fire for a page we created ourselves via context.new_page() -- _on_new_page
        # is idempotent (checks membership before appending), so this is safe even if it also fires.
        self._on_new_page(first_page)

    def _on_new_page(self, page: Page) -> None:
        if page not in self._pages:
            self._pages.append(page)
            page.set_default_timeout(BROWSER_ACTION_TIMEOUT_MS)
            page.on("dialog", self._on_dialog)
            page.on("download", self._on_download)
            page.on("framenavigated", lambda frame, p=page: self._on_frame_navigated(p, frame))
            logger.info("New tab opened: %s", page.url or "(blank)")
        self._active_index = self._pages.index(page)  # a new tab becomes active, matching normal browser UX
        self._notify_context_changed()

    def _on_dialog(self, dialog) -> None:
        logger.info("Auto-dismissing browser dialog (%s): %s", dialog.type, dialog.message)
        dialog.dismiss()

    def _on_download(self, download) -> None:
        Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
        save_path = str(Path(DOWNLOAD_DIR) / download.suggested_filename)
        try:
            download.save_as(save_path)
        except Exception:
            logger.warning("Failed to save download '%s'", download.suggested_filename, exc_info=True)
            return
        logger.info("Downloaded file saved to %s", save_path)
        self.recent_downloads.append(save_path)
        if len(self.recent_downloads) > MAX_TRACKED_DOWNLOADS:
            self.recent_downloads.pop(0)

    def _on_frame_navigated(self, page: Page, frame) -> None:
        if frame != page.main_frame:
            return  # ignore iframe navigation
        if page != self.page:
            return  # ignore background-tab navigation -- only the ACTIVE page's navigation invalidates cached state
        self._notify_context_changed()

    def add_context_change_listener(self, callback: Callable[[], None]) -> None:
        """
        Registers `callback` to be called whenever the active page's content might have
        changed out from under previously-cached state (navigation of the active page,
        tab switch, new tab becoming active, tab close). Subscribers should treat this
        as an unconditional "invalidate everything you cached about the previous page".
        """
        self._context_change_listeners.append(callback)

    def _notify_context_changed(self) -> None:
        for callback in self._context_change_listeners:
            try:
                callback()
            except Exception:
                logger.warning("A context-change listener raised", exc_info=True)

    @property
    def page(self) -> Page:
        """The currently active tab. Starts the browser on first access."""
        self._ensure_started()
        if not self._pages:
            raise RuntimeError("No pages available. Browser session may have been closed.")
        return self._pages[self._active_index]

    @property
    def pages(self) -> List[Page]:
        self._ensure_started()
        if self._pages is None:
            raise RuntimeError("Pages list is None. Browser session may have been closed.")
        return self._pages

    @property
    def active_index(self) -> int:
        return self._active_index

    def new_tab(self, url: Optional[str] = None) -> int:
        self._ensure_started()
        if self._context is None:
            raise RuntimeError("BrowserContext is not initialized. Browser session may have been closed.")
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
        self._notify_context_changed()

    def close_tab(self, index: Optional[int] = None) -> None:
        self._ensure_started()
        if self._context is None:
            raise RuntimeError("BrowserContext is not initialized. Browser session may have been closed.")
        idx = self._active_index if index is None else index
        if not (0 <= idx < len(self._pages)):
            raise IndexError(f"no tab at index {idx} ({len(self._pages)} tab(s) open)")
        self._pages[idx].close()
        del self._pages[idx]
        if not self._pages:
            self._on_new_page(self._context.new_page())  # never leave zero tabs open; also notifies
        else:
            self._active_index = min(self._active_index, len(self._pages) - 1)
            self._notify_context_changed()

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

# Safety net: nothing else in this codebase has an app-lifecycle shutdown hook to call
# default_session.close() from yet, so a crashed or killed process could otherwise leave an
# orphaned Chromium running. close() is already a no-op if the browser was never started.
atexit.register(default_session.close)
