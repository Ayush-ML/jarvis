# This Script is responsible for Element-based targeting on the current page -- the PREFERRED
# way to click/type on the page, over raw pixel coordinates. Same reasoning as
# computer_use/elements.py: visual coordinate estimation is unreliable, and a webpage adds its
# own extra fragility on top (responsive layouts, scroll position, zoom level all shift where
# something visually IS without changing what it structurally IS). DOM-based targeting sidesteps
# all of that.
#
# CACHE INVALIDATION: the label cache is cleared whenever session.py reports the active page's
# content might have changed (navigation, tab switch, new active tab, tab close) -- subscribed
# via default_session.add_context_change_listener() at import time. This assumes tools are used
# against `default_session` specifically (the shared singleton every other browser_use module
# also defaults to) -- a caller that passes a DIFFERENT BrowserSession instance wouldn't get
# cache invalidation tied to that session's own navigation, since the module-level cache here is
# effectively scoped to "the" default session, matching how every other default_* singleton in
# this codebase (rate_limiter, playback_reference) is used in practice.
#
# STALENESS VERIFICATION: list_interactive_elements() caches each element's tag + displayed text
# alongside its index. Before click_element/type_into_element/upload_file act, the CURRENT
# element at that index is re-checked against what was cached -- if the page changed enough that
# it no longer matches (DOM reordered, element replaced), the action is refused with a clear
# error instead of silently acting on whatever's there now. This is a real check, not just
# re-running the selector (Locator.nth() alone re-resolves position but doesn't verify identity).
from dataclasses import dataclass
from typing import Dict, List, Tuple

from src.tools.registry import Tool
from src.tools.browser_use.session import default_session, BrowserSession

INTERACTIVE_SELECTOR = (
    "a, button, input, select, textarea, "
    "[role=button], [role=link], [role=checkbox], [role=menuitem], [role=tab], "
    "[contenteditable=true], [onclick]"
)
MAX_ELEMENTS_LISTED = 60  # caps output for content-heavy pages
MAX_ELEMENT_TEXT_CHARS = 80  # keeps listings readable on elements with long inner text; also the comparison length for staleness checks


@dataclass
class _CachedElement:
    index: int
    tag: str
    text: str


# label (int) -> cached identity, from the most recent list_interactive_elements() call.
_element_cache: Dict[int, _CachedElement] = {}


def _invalidate_cache() -> None:
    _element_cache.clear()


default_session.add_context_change_listener(_invalidate_cache)


def _extract_tag_and_text(el) -> Tuple[str, str]:
    tag = el.evaluate("e => e.tagName.toLowerCase()")
    text = (
        (el.text_content() or "").strip()
        or (el.get_attribute("placeholder") or "").strip()
        or (el.get_attribute("aria-label") or "").strip()
        or (el.get_attribute("value") or "").strip()
    )
    return tag, text[:MAX_ELEMENT_TEXT_CHARS]


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
            tag, text = _extract_tag_and_text(el)
        except Exception:
            continue  # a single element failing to introspect shouldn't abort the whole scan

        label += 1
        _element_cache[label] = _CachedElement(index=index, tag=tag, text=text)
        lines.append(f"[{label}] <{tag}> '{text or '(no label)'}'")
        if label >= MAX_ELEMENTS_LISTED:
            lines.append(f"... truncated at {MAX_ELEMENTS_LISTED} elements; interact with what's shown first or narrow the page.")
            break

    if not lines:
        return "No interactive elements found on this page."
    return "Interactive elements:\n" + "\n".join(lines)


def _resolve_verified_locator(label: int, session: BrowserSession):
    """Returns (locator, None) on success, or (None, error_message) if the label is unknown or the element no longer matches what was listed."""
    cached = _element_cache.get(label)
    if cached is None:
        return None, f"Tool error: no element with label {label}. Call list_interactive_elements first."

    locator = session.page.locator(INTERACTIVE_SELECTOR).nth(cached.index)
    try:
        current_tag, current_text = _extract_tag_and_text(locator)
    except Exception as e:
        return None, f"Tool error: element [{label}] could not be found on the page anymore ({e}). The page likely changed -- call list_interactive_elements again."

    if current_tag != cached.tag or current_text != cached.text:
        return None, (
            f"Tool error: element [{label}] no longer matches what was listed "
            f"(expected <{cached.tag}> '{cached.text}', found <{current_tag}> '{current_text}'). "
            f"The page changed -- call list_interactive_elements again."
        )
    return locator, None


def click_element(label: int, session: BrowserSession = default_session) -> str:
    locator, error = _resolve_verified_locator(label, session)
    if error:
        return error
    if locator is None:
        return f"Tool error: locator is None for element {label}. Unable to click."
    try:
        locator.click()
    except Exception as e:
        return f"Tool error clicking element {label}: {e}"
    return f"Clicked element [{label}]."


def type_into_element(label: int, text: str, session: BrowserSession = default_session) -> str:
    locator, error = _resolve_verified_locator(label, session)
    if error:
        return error
    if locator is None:
        return f"Tool error: locator is None for element {label}. Unable to type."
    try:
        locator.fill(text)
    except Exception as e:
        return f"Tool error typing into element {label}: {e}"
    return f"Typed into element [{label}]: {text!r}"


def upload_file(label: int, files: List[str], session: BrowserSession = default_session) -> str:
    """For <input type="file"> elements specifically -- type_into_element's .fill() only works on text-editable elements and silently does nothing useful on a file input."""
    if not files:
        return "Tool error: files list is empty."
    locator, error = _resolve_verified_locator(label, session)
    if error:
        return error
    if locator is None:
        return f"Tool error: locator is None for element {label}. Unable to upload files."
    try:
        locator.set_input_files(files)
    except Exception as e:
        return f"Tool error uploading to element {label}: {e}"
    return f"Uploaded {len(files)} file(s) to element [{label}]: {files}"


TOOLS: List[Tool] = [
    Tool(
        name="list_interactive_elements",
        description="List clickable/typeable elements on the current page (links, buttons, inputs, etc.), found structurally via the DOM -- NOT by visually inspecting a screenshot. PREFER this over guessing pixel coordinates: click_element/type_into_element using the returned labels are far more reliable, since layout, scroll position, and zoom don't affect the underlying element structure. Call this again after any navigation, tab switch, or if an action reports the page changed.",
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
    Tool(
        name="upload_file",
        description="Upload one or more local files to a file input element (<input type=\"file\">), by label from list_interactive_elements. Use this instead of type_into_element for file inputs -- typing/filling does not work on them.",
        parameters={
            "type": "object",
            "properties": {
                "label": {"type": "integer", "description": "The [N] label shown by list_interactive_elements."},
                "files": {"type": "array", "items": {"type": "string"}, "description": "Absolute path(s) to the local file(s) to upload."},
            },
            "required": ["label", "files"],
        },
        handler=upload_file,
    ),
]
