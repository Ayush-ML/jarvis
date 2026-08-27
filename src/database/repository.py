# This Script is responsible for all Read/Write Access to the Database
# Each Repository wraps one Table and returns typed Models instead of raw sqlite3.Row objects
# Keeping every query here means nothing else in the codebase writes SQL directly
import json
from typing import Any, List, Optional
from src.database.db import Database
from src.database.models import Conversation, Message
from src.core.message_types import TextContent


class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, title: Optional[str] = None) -> Conversation | None:
        with self.db.cursor() as cur:
            cur.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
            new_id = cur.lastrowid
        return self.get(new_id)

    def get(self, conversation_id: int | None) -> Optional[Conversation]:
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

    def update_summary(self, conversation_id: int, summary: str, summarized_through_message_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """UPDATE conversations SET summary = ?, summarized_through_message_id = ?,
                   updated_at = datetime('now') WHERE id = ?""",
                (summary, summarized_through_message_id, conversation_id),
            )

    def delete(self, conversation_id: int) -> None:
        """Deletes the conversation; ON DELETE CASCADE (messages FK, PRAGMA foreign_keys=ON) removes its messages too."""
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, conversation_id: int, role: str, content: TextContent) -> Message:
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, json.dumps(content, ensure_ascii=False)),
            )
            message_id = cur.lastrowid
            cur.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cur.fetchone()
        return self._message_from_row(row)

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
        return [self._message_from_row(row) for row in rows]

    def mark_indexed(self, message_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("UPDATE messages SET indexed = 1 WHERE id = ?", (message_id,))

    def unindexed(self, limit: int = 200) -> List[Message]:
        """
        Messages persisted to SQLite but not yet embedded into the vector store --
        either because they were skipped on purpose (see ConversationService's
        role filter) or because indexing failed at write time. Used by
        ConversationService.backfill() to catch up.
        """
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT * FROM messages WHERE indexed = 0 ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        return [self._message_from_row(row) for row in rows]

    def count(self, conversation_id: int) -> int:
        """Cheap count used as a short-circuit before the heavier all_for_conversation() scan."""
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM messages WHERE conversation_id = ?", (conversation_id,))
            row = cur.fetchone()
        return row["c"]

    def all_for_conversation(self, conversation_id: int) -> List[Message]:
        """
        Every message in a conversation, oldest first. Used only by the
        summarization trigger to work out which turns have fallen outside
        HISTORY_WINDOW and still need folding into the summary -- guarded
        by count() so this doesn't run on every single turn.
        """
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            )
            rows = cur.fetchall()
        return [self._message_from_row(row) for row in rows]

    @staticmethod
    def _message_from_row(row: Any) -> Message:
        data = dict(row)
        data["content"] = MessageRepository._decode_content(data["content"])
        return Message(**data)

    @staticmethod
    def _decode_content(raw_content: Any) -> TextContent:
        """Return canonical content and upgrade legacy plain-text rows on read."""
        value: Any = raw_content
        if isinstance(raw_content, str):
            try:
                value = json.loads(raw_content)
            except json.JSONDecodeError:
                value = raw_content

        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return {
                "type": "text",
                "text": value["text"],
            }

        return {
            "type": "text",
            "text": str(value),
        }
