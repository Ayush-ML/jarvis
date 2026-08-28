# This Script is responsible for Element-based targeting on the current page -- the PREFERRED
# way to click/type on the page, over raw pixel coordinates. Same reasoning as
# computer_use/elements.py: visual coordinate estimation is unreliable, and a webpage adds its
# own extra fragility on top (responsive layouts, scroll position, zoom level all shift where
# something visually IS without changing what it structurally IS). DOM-based targeting sidesteps
# all of that.
#
# Built on Playwright Locators (page.locator(...).nth(index)), not cached ElementHandles --
# Locators re-run their selector query at the moment of each ACTION, which is the modern,
# recommended Playwright pattern specifically because it avoids acting on a stale/detached
# element. The one real limitation this does NOT solve: if the page's DOM changes between
# list_interactive_elements() and an action (elements added/removed/reordered), the cached
# INDEX can end up pointing at a different element than what was originally listed. That's an
# inherent risk of index-based caching across separate calls on a page that isn't guaranteed
# stable -- worth knowing, not something re-running the selector alone fixes.
from typing import Dict, List, Optional

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession

INTERACTIVE_SELECTOR = (
    "a, button, input, select, textarea, "
    "[role=button], [role=link], [role=checkbox], [role=menuitem], [role=tab], "
    "[contenteditable=true], [onclick]"
)
MAX_ELEMENTS_LISTED = 60  # caps output for content-heavy pages

# label (int) -> index into INTERACTIVE_SELECTOR's match order, from the most recent
# list_interactive_elements() call. Re-resolved into a fresh Locator on every action.
_element_cache: Dict[int, int] = {}


def list_interactive_elements(session: BrowserSession = default_session) -> str:
    page = session.page
    try:
        handles = page.query_selector_all(INTERACTIVE_SELECTOR)
    except Exception as e:
        return f"Tool error scanning page: {e}"

    _element_cache.clear()
    lines = []
    label = 0
    for index, el in enumerate(handles):
        try:
            if not el.is_visible():
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            text = (
                (el.text_content() or "").strip()
                or (el.get_attribute("placeholder") or "").strip()
                or (el.get_attribute("aria-label") or "").strip()
                or (el.get_attribute("value") or "").strip()
                or "(no label)"
            )
            text = text[:80]  # keep listings readable on elements with long inner text
        except Exception:
            continue  # a single element failing to introspect shouldn't abort the whole scan

        label += 1
        _element_cache[label] = index
        lines.append(f"[{label}] <{tag}> '{text}'")
        if label >= MAX_ELEMENTS_LISTED:
            lines.append(f"... truncated at {MAX_ELEMENTS_LISTED} elements; interact with what's shown first or narrow the page.")
            break

    if not lines:
        return "No interactive elements found on this page."
    return "Interactive elements:\n" + "\n".join(lines)


def click_element(label: int, session: BrowserSession = default_session) -> str:
    index = _element_cache.get(label)
    if index is None:
        return f"Tool error: no element with label {label}. Call list_interactive_elements first."
    try:
        locator = session.page.locator(INTERACTIVE_SELECTOR).nth(index)
        locator.click()
    except Exception as e:
        return f"Tool error clicking element {label}: {e}"
    return f"Clicked element [{label}]."


def type_into_element(label: int, text: str, session: BrowserSession = default_session) -> str:
    index = _element_cache.get(label)
    if index is None:
        return f"Tool error: no element with label {label}. Call list_interactive_elements first."
    try:
        locator = session.page.locator(INTERACTIVE_SELECTOR).nth(index)
        locator.fill(text)
    except Exception as e:
        return f"Tool error typing into element {label}: {e}"
    return f"Typed into element [{label}]: {text!r}"


TOOLS: List[Tool] = [
    Tool(
        name="list_interactive_elements",
        description="List clickable/typeable elements on the current page (links, buttons, inputs, etc.), found structurally via the DOM -- NOT by visually inspecting a screenshot. PREFER this over guessing pixel coordinates: click_element/type_into_element using the returned labels are far more reliable, since layout, scroll position, and zoom don't affect the underlying element structure.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=list_interactive_elements,
    ),
    Tool(
        name="click_element",
        description="Click a page element by the label number returned from the most recent list_interactive_elements call.",
        parameters={
            "type": "object",
            "properties": {"label": {"type": "integer", "description": "The [N] label shown by list_interactive_elements."}},
            "required": ["label"],
        },
        handler=click_element,
    ),
    Tool(
        name="type_into_element",
        description="Type text into a page element (e.g. a text input) by label from list_interactive_elements. Clears any existing value first.",
        parameters={
            "type": "object",
            "properties": {
                "label": {"type": "integer", "description": "The [N] label shown by list_interactive_elements."},
                "text": {"type": "string", "description": "Text to enter into the field."},
            },
            "required": ["label", "text"],
        },
        handler=type_into_element,
    ),
]
