# This Script is responsible for Read-only Filesystem operations: reading file contents,
# listing directories, walking directory trees, searching by glob pattern, and inspecting
# file metadata. See file_system/__init__.py for the module-wide access-policy note.
import fnmatch
from datetime import datetime
from typing import List, Optional
import base64, mimetypes
from src.tools.registry import Tool
from src.tools.file_system.common import resolve_path
from src.core.config import MAX_SEARCH_RESULTS, MAX_TREE_ENTRIES

def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{int(size)}B" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def read_text_file(path: str, head: Optional[int] = None, tail: Optional[int] = None, encoding: str = "utf-8") -> str:
    if head is not None and tail is not None:
        return "Tool error: specify head or tail, not both."
    p = resolve_path(path)
    if not p.exists():
        return f"Tool error: '{p}' does not exist."
    if not p.is_file():
        return f"Tool error: '{p}' is not a file."
    try:
        text = p.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return f"Tool error: '{p}' does not appear to be a text file (failed to decode as {encoding})."
    lines = text.splitlines()
    if head is not None:
        lines = lines[:head]
    elif tail is not None:
        lines = lines[-tail:]
    return "\n".join(lines)

def read_media_file(path: str) -> str:
    p = resolve_path(path=path)

    try:
        if not p.is_file():
            return "This path either does not or is not a file"

        mime_type, _ = mimetypes.guess_type(p.name)
        if mime_type is None:
            return "Could Not guess the Mime Type of this File"

        media_type, _ = mime_type.split("/", 1)
        if media_type not in {"image", "video", "audio"}:
            return "This Media Type is Unsupported"

        file_bytes = p.read_bytes()
        b64_data = base64.b64encode(file_bytes).decode("utf-8")

    except Exception as e:
        return f"Exception Occoured when Reading Media File as e"

    return f"data:{mime_type};base64,{b64_data}"


def read_multiple_files(paths: List[str]) -> str:
    """Reads several files at once. A failure on one file doesn't stop the others."""
    parts = []
    for path in paths:
        p = resolve_path(path)
        try:
            if not p.is_file():
                parts.append(f"--- {p} ---\n[Tool error: not a file or does not exist]")
                continue
            content = p.read_text(encoding="utf-8")
            parts.append(f"--- {p} ---\n{content}")
        except Exception as e:
            parts.append(f"--- {p} ---\n[Tool error: {e}]")
    return "\n\n".join(parts)


def list_directory(path: str) -> str:
    p = resolve_path(path)
    if not p.exists():
        return f"Tool error: '{p}' does not exist."
    if not p.is_dir():
        return f"Tool error: '{p}' is not a directory."
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    if not entries:
        return f"'{p}' is empty."
    lines = []
    for e in entries:
        if e.is_dir():
            lines.append(f"[DIR]  {e.name}")
        else:
            try:
                size = _human_size(e.stat().st_size)
            except OSError:
                size = "?"
            lines.append(f"[FILE] {e.name} ({size})")
    return f"Contents of '{p}':\n" + "\n".join(lines)


def directory_tree(path: str, max_depth: int = 4, exclude: Optional[List[str]] = None) -> str:
    p = resolve_path(path)
    if not p.exists():
        return f"Tool error: '{p}' does not exist."
    if not p.is_dir():
        return f"Tool error: '{p}' is not a directory."

    excludes = []
    lines: List[str] = []
    count = 0
    truncated = False

    def walk(current, depth: int, prefix: str) -> None:
        nonlocal count, truncated
        if truncated or depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError as e:
            lines.append(f"{prefix}[error reading directory: {e}]")
            return
        for e in entries:
            if e.name in excludes:
                continue
            if count >= MAX_TREE_ENTRIES:
                truncated = True
                return
            count += 1
            marker = "DIR " if e.is_dir() else "FILE"
            lines.append(f"{prefix}[{marker}] {e.name}")
            if e.is_dir():
                walk(e, depth + 1, prefix + "  ")

    walk(p, 0, "")
    result = f"Tree of '{p}':\n" + "\n".join(lines)
    if truncated:
        result += f"\n... truncated at {MAX_TREE_ENTRIES} entries."
    return result


def search_files(path: str, pattern: str) -> str:
    p = resolve_path(path)
    if not p.exists() or not p.is_dir():
        return f"Tool error: '{p}' is not a valid directory."
    matches = []
    for candidate in p.rglob("*"):
        if fnmatch.fnmatch(candidate.name, pattern):
            matches.append(str(candidate))
            if len(matches) >= MAX_SEARCH_RESULTS:
                break
    if not matches:
        return f"No files matching '{pattern}' found under '{p}'."
    result = f"Found {len(matches)} match(es):\n" + "\n".join(matches)
    if len(matches) >= MAX_SEARCH_RESULTS:
        result += f"\n... capped at {MAX_SEARCH_RESULTS} results, narrow the pattern or path for more."
    return result


def get_file_info(path: str) -> str:
    p = resolve_path(path)
    if not p.exists():
        return f"Tool error: '{p}' does not exist."
    stat = p.stat()
    kind = "directory" if p.is_dir() else "file"
    # st_ctime is creation time on Windows specifically (this project is Windows-only) --
    # on POSIX it would mean something different (last metadata change), worth knowing if this
    # code is ever ported.
    created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    size = _human_size(stat.st_size) if p.is_file() else "-"
    return f"Path: {p}\nType: {kind}\nSize: {size}\nCreated: {created}\nModified: {modified}"


TOOLS: List[Tool] = [
    Tool(
        name="read_file",
        description="Read a text file's contents. Use head or tail to read only the first/last N lines of a large file instead of the whole thing.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."},
                "head": {"type": "integer", "description": "Return only the first N lines."},
                "tail": {"type": "integer", "description": "Return only the last N lines."},
            },
            "required": ["path"],
        },
        handler=read_text_file,
    ),
    Tool(
        name="read_multiple_files",
        description="Read several text files in one call. A failure reading one file doesn't stop the others -- each result is labeled with its path.",
        parameters={
            "type": "object",
            "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "Paths to read."}},
            "required": ["paths"],
        },
        handler=read_multiple_files,
    ),
    Tool(
        name="list_directory",
        description="List the immediate contents of a directory, with file sizes.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Directory to list."}},
            "required": ["path"],
        },
        handler=list_directory,
    ),
    Tool(
        name="directory_tree",
        description="Recursively list a directory's contents as a tree. Depth and total entries are capped to avoid overwhelming output on large trees; common noise directories (.git, node_modules, __pycache__, venv) are excluded by default.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root directory to walk."},
                "max_depth": {"type": "integer", "description": "Maximum recursion depth. Default 4."},
                "exclude": {"type": "array", "items": {"type": "string"}, "description": "Additional directory/file names to skip, beyond the built-in noise excludes."},
            },
            "required": ["path"],
        },
        handler=directory_tree,
    ),
    Tool(
        name="search_files",
        description="Recursively search a directory for files matching a glob pattern (e.g. '*.py', 'test_*').",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to search under."},
                "pattern": {"type": "string", "description": "Glob pattern to match filenames against (e.g. '*.txt')."},
            },
            "required": ["path", "pattern"],
        },
        handler=search_files,
    ),
    Tool(
        name="get_file_info",
        description="Get metadata for a file or directory: type, size, created and modified timestamps.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to inspect."}},
            "required": ["path"],
        },
        handler=get_file_info,
    ),
    Tool(
        name="read_media_file",
        description="Inject the Media File that is on the Given Path into Conext to be available for viewing",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path of the Media File to View"}},
            "required": ["path"]
        },
        handler=read_media_file
    )
]