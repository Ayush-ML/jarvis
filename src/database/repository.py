# This Script is responsible for all Read/Write Access to the Database
# Each Repository wraps one Table and returns typed Models instead of raw sqlite3.Row objects
# Keeping every query here means nothing else in the codebase writes SQL directly
from typing import List, Optional
from src.database.db import Database
from src.database.models import Conversation, Message, Memory


class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, title: Optional[str] = None) -> Conversation:
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
            new_id = cur.lastrowid
        return self.get(new_id)

    def get(self, conversation_id: int) -> Optional[Conversation]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cur.fetchone()
        return Conversation(**dict(row)) if row else None

    def touch(self, conversation_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                (conversation_id,),
            )


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, conversation_id: int, role: str, content: str) -> Message:
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )
            message_id = cur.lastrowid
            cur.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cur.fetchone()
        return Message(**dict(row))

    def recent(self, conversation_id: int, limit: int) -> List[Message]:
        """Most recent `limit` messages for a conversation, oldest first."""
        with self.db.cursor() as cur:
            cur.execute(
                """SELECT * FROM (
                       SELECT * FROM messages WHERE conversation_id = ?
                       ORDER BY id DESC LIMIT ?
                   ) ORDER BY id ASC""",
                (conversation_id, limit),
            )
            rows = cur.fetchall()
        return [Message(**dict(row)) for row in rows]


class MemoryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        content: str,
        kind: str = "fact",
        importance: float = 0.5,
        source_message_id: Optional[int] = None,
    ) -> Memory:
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO memories (content, kind, importance, source_message_id)
                   VALUES (?, ?, ?, ?)""",
                (content, kind, importance, source_message_id),
            )
            memory_id = cur.lastrowid
            cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
            row = cur.fetchone()
        return Memory(**dict(row))

    def search(self, query: str, top_k: int = 5) -> List[Memory]:
        """
        FTS5/BM25-ranked keyword search over stored memories. An empty
        result is a normal outcome (no relevant memories yet), not an error.
        """
        with self.db.cursor() as cur:
            cur.execute(
                """SELECT m.* FROM memories m
                   JOIN memories_fts f ON f.rowid = m.id
                   WHERE memories_fts MATCH ?
                   ORDER BY bm25(memories_fts) LIMIT ?""",
                (self._sanitize(query), top_k),
            )
            rows = cur.fetchall()
        memories = [Memory(**dict(row)) for row in rows]
        if memories:
            self._mark_accessed([m.id for m in memories])
        return memories

    def _mark_accessed(self, ids: List[int]) -> None:
        with self.db.cursor() as cur:
            cur.executemany(
                """UPDATE memories SET access_count = access_count + 1,
                   last_accessed_at = datetime('now') WHERE id = ?""",
                [(i,) for i in ids],
            )

    @staticmethod
    def _sanitize(query: str) -> str:
        # FTS5 treats punctuation as query syntax; quoting each token lets
        # raw user input (questions, contractions, symbols) through safely
        tokens = [t for t in query.replace('"', " ").split() if t]
        return " OR ".join(f'"{t}"' for t in tokens) or '""'
