# This Script is responsible for Launching applications, files, and URLs via the system default handler.
import os
from typing import List

from src.tools.registry import Tool


def open_application(path: str) -> str:
    """path can be an executable, a file (opens with its default app), or a URL."""
    try:
        os.startfile(path)
    except OSError as e:
        return f"Tool error: could not open '{path}' ({e})."
    return f"Opened: {path}"


TOOLS: List[Tool] = [
    Tool(
        name="open_application",
        description="Open an application, file, or URL using the system default handler (e.g. an .exe path, a document, or a web URL).",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to an executable/file, or a URL."}},
            "required": ["path"],
        },
        handler=open_application,
    ),
]
