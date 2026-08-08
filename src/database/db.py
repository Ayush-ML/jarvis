# This Script is responsible for owning the SQLite Connection for the Jarvis Project
# It handles Schema Creation/Migrations and exposes a single Connection Point for all Repositories
# Repositories own their queries; this class only owns the connection and the schema
# Importing Necessary Libraries
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from src.core.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    summary TEXT,
    summarized_through_message_id INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    indexed INTEGER NOT NULL DEFAULT 0
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
        # check_same_thread=False lets multiple threads (voice loop, a skill,
        # the main chat loop) share one connection -- but sqlite3 connections
        # aren't internally thread-safe for concurrent writes, so every access
        # goes through this lock rather than relying on SQLite's own locking.
        self._lock = threading.Lock()
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """
        Minimal additive migrations for anyone upgrading an existing jarvis.db
        created before a column existed. Each statement is guarded so running
        this against an already-migrated database is a harmless no-op.
        """
        migrations = [
            "ALTER TABLE messages ADD COLUMN indexed INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE conversations ADD COLUMN summary TEXT",
            "ALTER TABLE conversations ADD COLUMN summarized_through_message_id INTEGER NOT NULL DEFAULT 0",
        ]
        for stmt in migrations:
            try:
                self._conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        with self._lock:
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
