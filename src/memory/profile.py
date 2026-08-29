# This Script is responsible for loading and writing the two Markdown files that define Jarvis's
# persona and the user's profile. SOUL.md is Jarvis's system prompt (identity, tone, rules) and
# is meant to be hand-edited -- nothing writes to it. USER.md is a durable profile of the user,
# unconditionally injected into every turn's context when non-empty (see brain/context_manager.py)
# -- read AND written here. The writer functions below are the USER.md writer that's been
# deliberately deferred since USER.md was first introduced in this project; every prior mention
# of it noted "nothing writes to it yet, on purpose." src/tools/memory/profile_tools.py is what
# actually exposes these to the model as tools.
import threading
from pathlib import Path
from typing import Optional
from src.core.config import SOUL_PATH, USER_PROFILE_PATH

DEFAULT_SOUL = "You are Jarvis, a helpful personal AI assistant."
USER_PROFILE_HEADER = "# USER\n\n"

# Guards read-modify-write on USER.md -- a tool call could plausibly run on a different thread
# than whatever else touches this file (e.g. a future concurrent voice + text session), and a
# race on a plain read-then-write would silently drop one side's edit.
_user_profile_lock = threading.Lock()


def load_soul(path: str = SOUL_PATH) -> str:
    file = Path(path)
    if not file.exists():
        return DEFAULT_SOUL
    return file.read_text(encoding="utf-8").strip() or DEFAULT_SOUL


def load_user_profile(path: str = USER_PROFILE_PATH) -> Optional[str]:
    """None if no profile exists yet -- ContextManager should skip it, not inject an empty block."""
    file = Path(path)
    if not file.exists():
        return None
    content = file.read_text(encoding="utf-8").strip()
    return content or None


def get_user_profile_text(path: str = USER_PROFILE_PATH) -> str:
    """Tool-facing variant of load_user_profile -- always returns a human-readable string, never None, since a tool call needs an answer either way."""
    return load_user_profile(path) or "No facts remembered about the user yet."


def remember_user_fact(fact: str, path: str = USER_PROFILE_PATH) -> str:
    """
    Appends `fact` as a new bullet line in USER.md, creating the file with a
    header if it doesn't exist yet. Skips (rather than duplicates) an EXACT
    repeat of an existing line -- this is not near-duplicate detection (e.g.
    "likes coffee" and "enjoys coffee" would both get stored); that needs
    semantic comparison, which a plain file-append tool doesn't attempt.
    """
    fact = fact.strip()
    if not fact:
        return "Tool error: fact is empty."

    file = Path(path)
    with _user_profile_lock:
        content = file.read_text(encoding="utf-8") if file.exists() else USER_PROFILE_HEADER

        bullet = f"- {fact}"
        if bullet in [line.strip() for line in content.splitlines()]:
            return f"Already remembered: {fact}"

        if not content.endswith("\n"):
            content += "\n"
        content += bullet + "\n"

        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    return f"Remembered: {fact}"


def forget_user_fact(fact_substring: str, path: str = USER_PROFILE_PATH) -> str:
    """
    Removes the ONE bullet line in USER.md containing `fact_substring`
    (case-insensitive). Refuses on zero or multiple matches rather than
    guessing which one was meant -- same discipline as requiring a unique
    match before an edit, to avoid silently deleting the wrong fact.
    """
    file = Path(path)
    with _user_profile_lock:
        if not file.exists():
            return "Tool error: no user profile exists yet -- nothing to forget."

        lines = file.read_text(encoding="utf-8").splitlines()
        needle = fact_substring.strip().lower()
        matches = [i for i, line in enumerate(lines) if line.strip().startswith("-") and needle in line.lower()]

        if not matches:
            return f"Tool error: no remembered fact matching '{fact_substring}'."
        if len(matches) > 1:
            matched_text = "\n".join(lines[i] for i in matches)
            return f"Tool error: '{fact_substring}' matches multiple facts -- be more specific:\n{matched_text}"

        removed = lines.pop(matches[0])
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return f"Forgot: {removed.lstrip('- ').strip()}"
