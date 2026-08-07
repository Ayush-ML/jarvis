# This Script is responsible for loading the two Markdown files that define Jarvis's persona
# and the user's profile. SOUL.md is Jarvis's system prompt (identity, tone, rules) and is
# meant to be hand-edited. USER.md is a profile of the user -- read here only; nothing writes
# to it yet, that's a separate, not-yet-built feature.
from pathlib import Path
from typing import Optional
from src.core.config import SOUL_PATH, USER_PROFILE_PATH

DEFAULT_SOUL = "You are Jarvis, a helpful personal AI assistant."


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
