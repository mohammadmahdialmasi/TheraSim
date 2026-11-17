"""Repository for sequential simulation sessions."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository


SESSION_STATUSES = {
    "initialized",
    "active",
    "completed",
    "interrupted",
    "failed",
}


class SessionOrderError(RuntimeError):
    """A previous session does not permit starting the next session."""


class SessionRepository(ConnectionBoundRepository):
    """Stores sessions and exposes deterministic sequence checks."""

    def create_session(
        self,
        *,
        session_id: str,
        run_id: str,
        session_number: int,
        created_at: str,
        status: str = "initialized",
        transcript_version: int = 1,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> None:
        self.require_text(session_id, "session_id")
        self.require_text(run_id, "run_id")
        self.require_text(created_at, "created_at")

        if isinstance(session_number, bool) or not isinstance(
            session_number, int
        ):
            raise ValueError("Session number must be an integer.")

        if session_number < 1:
            raise ValueError("Session number must be a positive integer.")

        if status not in SESSION_STATUSES:
            raise ValueError("Invalid session status.")

        if isinstance(transcript_version, bool) or not isinstance(
            transcript_version, int
        ) or transcript_version < 1:
            raise ValueError("Transcript version must be a positive integer.")

        self._connection.execute(
            """
            INSERT INTO sessions (
                session_id, run_id, session_number,
                status, transcript_version,
                started_at, ended_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                run_id,
                session_number,
                status,
                transcript_version,
                started_at,
                ended_at,
                created_at,
            ),
        )

    def get_session(self, session_id: str) -> sqlite3.Row | None:
        self.require_text(session_id, "session_id")

        return self._connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")

        return list(
            self._connection.execute(
                """
                SELECT * FROM sessions
                WHERE run_id = ?
                ORDER BY session_number
                """,
                (run_id,),
            ).fetchall()
        )

    def next_session_number(self, run_id: str) -> int:
        """Return the next legal number if all prior sessions are completed."""

        sessions = self.list_by_run(run_id)

        if not sessions:
            return 1

        numbers = [row["session_number"] for row in sessions]
        expected = list(range(1, len(numbers) + 1))

        if numbers != expected:
            raise SessionOrderError(
                "Existing session numbers are not sequential."
            )

        if sessions[-1]["status"] != "completed":
            raise SessionOrderError(
                "The previous session must be completed first."
            )

        next_number = numbers[-1] + 1
        return next_number

    def create_next_session(
        self,
        *,
        session_id: str,
        run_id: str,
        created_at: str,
        status: str = "active",
        started_at: str | None = None,
    ) -> int:
        """Create the next session inside the caller's transaction."""

        number = self.next_session_number(run_id)

        self.create_session(
            session_id=session_id,
            run_id=run_id,
            session_number=number,
            created_at=created_at,
            status=status,
            started_at=started_at,
        )

        return number

    def update_status(
        self,
        session_id: str,
        status: str,
        *,
        started_at: str | None = None,
        ended_at: str | None = None,
        transcript_hash: str | None = None,
    ) -> bool:
        self.require_text(session_id, "session_id")

        if status not in SESSION_STATUSES:
            raise ValueError("Invalid session status.")

        assignments = ["status = ?"]
        values: list[object] = [status]

        if started_at is not None:
            self.require_text(started_at, "started_at")
            assignments.append("started_at = ?")
            values.append(started_at)

        if ended_at is not None:
            self.require_text(ended_at, "ended_at")
            assignments.append("ended_at = ?")
            values.append(ended_at)

        if transcript_hash is not None:
            self.require_text(transcript_hash, "transcript_hash")
            assignments.append("transcript_hash = ?")
            values.append(transcript_hash)

        values.append(session_id)

        cursor = self._connection.execute(
            f"""
            UPDATE sessions
            SET {", ".join(assignments)}
            WHERE session_id = ?
            """,
            values,
        )

        return cursor.rowcount == 1
