# This Script is responsible for Element-based UI targeting via Windows' UI Automation tree --
# the PREFERRED way to click/type into UI elements, over raw pixel coordinates (see mouse.py,
# keyboard.py). Most models are genuinely unreliable at estimating pixel coordinates from a
# screenshot -- visual-spatial grounding is a well-known weak point across vision-language
# models. This sidesteps that entirely: element positions are read structurally via pywinauto,
# not estimated visually. Not every window exposes a useful UIA tree (games, canvas-rendered
# UIs, some Electron apps) -- an empty list_interactive_elements result means fall back to
# mouse.py/keyboard.py's coordinate-based tools.
import re
from typing import Any, Dict, List, Optional

import pygetwindow as gw
from pywinauto import Desktop

from src.tools.registry import Tool

INTERACTIVE_CONTROL_TYPES = {
    "Button", "Edit", "ComboBox", "CheckBox", "RadioButton", "Hyperlink",
    "MenuItem", "ListItem", "TabItem", "Slider", "Spinner",
}
MAX_ELEMENTS_LISTED = 60  # caps output for complex windows (e.g. browsers) that can expose hundreds of UIA nodes

# label (int) -> pywinauto control wrapper, populated by the most recent list_interactive_elements()
# call. click_element/type_into_element re-resolve the control's CURRENT position at action time
# (pywinauto queries the live element, not a cached coordinate) -- more robust than baking in a
# position that could go stale if the window moved between the list call and the action.
_element_cache: Dict[int, Any] = {}


def _resolve_window(window_title: Optional[str]):
    """Returns a pywinauto UIA window wrapper for `window_title`, or the currently active window if omitted."""
    title = window_title
    if title is None:
        active = gw.getActiveWindow()
        if active is None:
            raise RuntimeError("no window is currently active/focused")
        title = active.title
    return Desktop(backend="uia").window(title_re=f".*{re.escape(title)}.*")


def list_interactive_elements(window_title: Optional[str] = None) -> str:
    """
    Enumerates clickable/typeable elements in a window via Windows' UI Automation
    tree -- structural, not visual. Populates the label cache click_element/
    type_into_element read from.
    """
    try:
        window = _resolve_window(window_title)
    except Exception as e:
        return f"Tool error: could not find window ({e})."

    _element_cache.clear()
    lines = []
    label = 0
    try:
        for ctrl in window.descendants():
            info = ctrl.element_info
            if info.control_type not in INTERACTIVE_CONTROL_TYPES or not ctrl.is_visible():
                continue
            rect = info.rectangle
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            label += 1
            _element_cache[label] = ctrl
            name = info.name or "(no label)"
            cx, cy = rect.mid_point()
            lines.append(f"[{label}] {info.control_type} '{name}' at ({cx}, {cy})")
            if label >= MAX_ELEMENTS_LISTED:
                lines.append(f"... truncated at {MAX_ELEMENTS_LISTED} elements; narrow window_title or interact with what's shown first.")
                break
    except Exception as e:
        # UIA tree walks can genuinely fail partway through on some apps (e.g. a window
        # closing mid-scan) -- whatever was found before the failure is still useful.
        if not lines:
            return f"Tool error while scanning window: {e}"

    if not lines:
        return "No interactive elements found in this window."
    return "Interactive elements:\n" + "\n".join(lines)


def click_element(label: int) -> str:
    ctrl = _element_cache.get(label)
    if ctrl is None:
        return f"Tool error: no element with label {label}. Call list_interactive_elements first."
    try:
        ctrl.click_input()  # click_input (real synthesized mouse event) is more broadly compatible than click() (a posted WM_CLICK message some UI frameworks ignore)
    except Exception as e:
        return f"Tool error clicking element {label}: {e}"
    return f"Clicked element [{label}] ({ctrl.element_info.control_type} '{ctrl.element_info.name}')."


def type_into_element(label: int, text: str) -> str:
    ctrl = _element_cache.get(label)
    if ctrl is None:
        return f"Tool error: no element with label {label}. Call list_interactive_elements first."
    try:
        ctrl.click_input()  # focus it first -- typing without focus lands wherever focus already was
        ctrl.type_keys(text, with_spaces=True)
    except Exception as e:
        return f"Tool error typing into element {label}: {e}"
    return f"Typed into element [{label}]: {text!r}"


TOOLS: List[Tool] = [
    Tool(
        name="list_interactive_elements",
        description="List clickable/typeable UI elements (buttons, text fields, links, checkboxes, etc.) in a window, found via Windows' accessibility tree -- NOT by visually inspecting a screenshot. PREFER this over guessing pixel coordinates: click_element/type_into_element using the returned labels are far more reliable than click(x, y) with coordinates estimated by eye. Not every window exposes a useful tree (games, canvas apps) -- an empty result means fall back to coordinate-based tools.",
        parameters={
            "type": "object",
            "properties": {
                "window_title": {"type": "string", "description": "Full or partial title of the window to scan. Omit to scan the currently active/focused window."},
            },
            "required": [],
        },
        handler=list_interactive_elements,
    ),
    Tool(
        name="click_element",
        description="Click a UI element by the label number returned from the most recent list_interactive_elements call. Preferred over click(x, y) -- re-resolves the element's real position at click time rather than relying on a coordinate estimated from a screenshot.",
        parameters={
            "type": "object",
            "properties": {"label": {"type": "integer", "description": "The [N] label shown by list_interactive_elements."}},
            "required": ["label"],
        },
        handler=click_element,
    ),
    Tool(
        name="type_into_element",
        description="Focus a specific UI element (by label from list_interactive_elements) and type text into it. Preferred over type_text -- guarantees the text lands in the intended field.",
        parameters={
            "type": "object",
            "properties": {
                "label": {"type": "integer", "description": "The [N] label shown by list_interactive_elements."},
                "text": {"type": "string", "description": "Text to type into the focused element."},
            },
            "required": ["label", "text"],
        },
        handler=type_into_element,
    ),
]
