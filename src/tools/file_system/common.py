# This Script is responsible for shared path handling used across every file_system tool module.
# Genuinely shared, unlike computer_use's split (which happened to leave nothing in common) --
# every read/write/manage operation needs identical path resolution, so it lives in one place.
from pathlib import Path


def resolve_path(path: str) -> Path:
    """Expands ~ and resolves to an absolute, canonical path -- so tool output always shows exactly what was operated on, with no ambiguity from relative paths or symlinks."""
    return Path(path).expanduser().resolve()
