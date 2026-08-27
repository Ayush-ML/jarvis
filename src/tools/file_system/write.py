# This Script is responsible for Write-only Filesystem operations: creating or completely overwriting a file,
# creating a directory, moving a file from one place to another, deleting a file, and editing
# a file. See file_system/__init__.py for the module-wide access-policy note.

from src.tools.file_system.common import resolve_path
import os
from tempfile import NamedTemporaryFile
from typing import Optional, List, Dict
import shutil
from src.tools.registry import Tool

def write_file(path: str, data: str, encoding: Optional[str] = "utf-8") -> str:
    p = resolve_path(path=path)
    dir = os.path.dirname(p=p)

    with NamedTemporaryFile('w', dir=dir, encoding=encoding, delete=False) as temp_file:
        temp_file.write(data)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_path = temp_file.name

    try:
        os.replace(temp_path, p)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return f"Exception Occoured during File Writing as {e}"

    return "File has Been Written Successfully, Encountered no Exceptions"

def delete_file(path: str) -> str:
    p = resolve_path(path=path)

    try:
        if not p.is_file():
            return "This Path does not lead to a File, If you are trying to delete a directory, use the delete_dir tool instead"

        p.unlink()
    except Exception as e:
        return f"Exception Occoured while Deleting File as {e}"

    return "File Has Been Deleted Successfully, Encountered no Exceptions"

def delete_dir(path: str) -> str:
    p = resolve_path(path=path)

    try:
        if not p.is_dir():
            return "This Path does not lead to a Directory, If you are trying to delete a File, use the delete_file tool instead"

        shutil.rmtree(path=p)
    except Exception as e:
        return f"Exception Occoured while Deleting directory as {e}"

    return "Directory has been deleted Successfully, Encountered no Exceptions"

def create_dir(path: str, parents: bool = True) -> str:
    p = resolve_path(path=path)

    try:
        p.mkdir(parents=parents, exist_ok=True)
    except Exception as e:
        return f"Exception Occoured when Creating the Directory as {e}"

    return "Directory has Been Created Successfullt, Encountered no Exceptions"

def edit_file(path: str, edits: List[Dict[str, str]], encoding: Optional[str] = "utf-8") -> str:
    p = resolve_path(path=path)

    try:
        if not p.is_file():
            return "File in the Path specified does not exist"
        if not edits:
            return "No edits have been Provided, Doing Nothing"

        content = p.read_text(encoding=encoding)
        num_edits = 0

        for edit in edits:
            old_text = edit['old_text']
            new_text = edit['new_text']
            count = int(edit['count'])

            if old_text is None or new_text is None or count is None:
                continue
            if old_text not in content:
                continue

            content = content.replace(old_text, new_text, count)
            num_edits += 1

        p.write_text(data=content, encoding=encoding)

    except Exception as e:
        return f"Encountered Exception when Editing the File as {e}"

    return f"{num_edits} out of {len(edits)} Completed Successfully, Encountered no Exceptions in the Process"

TOOLS: List[Tool] = [
    Tool(
        name="write_file",
        description="Atomically Writes all Given Data to a File and Creates the File if it does not Exist",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The Path where The File to be written to or Created is located"
                },
                "data": {
                    "type": "string",
                    "description": "The Data that is to be written into the File"
                },
                "encoding": {
                    "type": "string",
                    "description": "The Encoding type of the data written, utf-8 is the default"
                }
            },
            "required": ["path", "data"]
        },
        handler=write_file
    ),
    Tool(
            name="delete_file",
            description="Deletes the Entire File of the given path, this is IRREVERSIBLE, use CAUTIOUSLY",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The Path where The File to be deleted is located"
                    }
                },
                "required": ["path"]
            },
            handler=delete_file
    ),
    Tool(
            name="delete_dir",
            description="Deletes the Directory specified in the path as well as ALL sub directories, use VERY CAUTIOUSLY",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The Path where The Directory to be deleted is located"
                    }
                },
                "required": ["path"]
            },
            handler=delete_dir
    ),
    Tool(
            name="create_dir",
            description="Creates a Directory and all its Parents unless specified other wise",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The Path where The Directory to be created is located"
                    },
                    "parents": {
                        "type": "boolean",
                        "description": "Whether to Create all Parent Directories of the Directory to be created or not, Default is True"
                    }
                },
                "required": ["path"]
            },
            handler=create_dir
    ),
    Tool(
            name="edit_file",
            description="Edits the File located in the path specified using all the Given Edits and Number of Occourneces to Edit",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The path of the file to be edited."
                    },
                    "edits": {
                        "type": "array",
                        "description": "A list of text edits to apply to the file.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_text": {
                                    "type": "string",
                                    "description": "The exact text to be replaced."
                                },
                                "new_text": {
                                    "type": "string",
                                    "description": "The text to replace old_text with."
                                },
                                "count": {
                                    "type": "integer",
                                    "description": "How Many Occourences of the Given Old Text to Change into the New Text"
                                }
                            },
                            "required": ["old_text", "new_text", "count"]
                        }
                    }
                },
                "required": ["path", "edits"],
            },
            handler=edit_file
    )
]