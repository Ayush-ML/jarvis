# This Script is responsible for owning the SQLite Connection for the Jarvis Project
# It handles Schema Creation/Migrations and exposes a single Connection Point for all Repositories
# Repositories own their queries; this class only owns the connection and the schema
# Importing Necessary Libraries
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from src.core.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
"""

# NOTE: no embeddings or "memories" table here on purpose. SQLite is the source of
# truth for conversation history only. Semantic search over all past sessions is
# handled entirely by the local vector store (see src/memory/vector_store.py),
# which keeps its own persisted index of message content.


class Database:
    """
    Owns the single SQLite connection for the application and exposes a
    context-managed cursor for Repositories to use. Deliberately thin:
    it knows how to connect and migrate, nothing about what's stored.
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    def close(self) -> None:
        self._conn.close()
