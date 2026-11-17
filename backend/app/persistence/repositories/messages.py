"""Repository for immutable-preserving conversation message records."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository


MESSAGE_ROLES = {"therapist", "patient"}


class MessageRepository(ConnectionBoundRepository):
    """Stores therapist and patient transcript messages."""

    def create_message(
        self,
        *,
        message_id: str,
        session_id: str,
        sequence_number: int,
        role: str,
        content: str,
        created_at: str,
        model_run_id: str | None = None,
        content_hash: str | None = None,
    ) -> None:
        for name, value in (
            ("message_id", message_id),
            ("session_id", session_id),
            ("content", content),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        if isinstance(sequence_number, bool) or not isinstance(
            sequence_number, int
        ) or sequence_number < 1:
            raise ValueError("Sequence number must be a positive integer.")

        if role not in MESSAGE_ROLES:
            raise ValueError("Invalid message role.")

        self._connection.execute(
            """
            INSERT INTO messages (
                message_id, session_id, sequence_number,
                role, content, model_run_id,
                content_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                sequence_number,
                role,
                content,
                model_run_id,
                content_hash,
                created_at,
            ),
        )

    def get_message(self, message_id: str) -> sqlite3.Row | None:
        self.require_text(message_id, "message_id")

        return self._connection.execute(
            "SELECT * FROM messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()

    def list_by_session(
        self,
        session_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        self.require_text(session_id, "session_id")
        self.require_pagination(limit, offset)

        return list(
            self._connection.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY sequence_number
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset),
            ).fetchall()
        )

    def count_by_session(self, session_id: str) -> int:
        self.require_text(session_id, "session_id")

        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        return int(row[0])
    def next_sequence_number(self, session_id: str) -> int:
        self.require_text(session_id, "session_id")

        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(sequence_number), 0) + 1
            FROM messages
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()

        return int(row[0])
