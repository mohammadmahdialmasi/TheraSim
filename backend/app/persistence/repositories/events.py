"""Repository for application and behavioral event records."""

import sqlite3
from collections.abc import Mapping

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    json_text,
    require_message_for_run,
    require_offsets,
    require_session_for_run,
    require_text,
)


EVENT_METHODS = {"application_rule", "model_assisted", "manual"}
EVENT_STATUSES = {"candidate", "accepted", "rejected", "requires_review"}


class EventRepository(ConnectionBoundRepository):
    def next_sequence_number(self, run_id: str) -> int:
        self.require_text(run_id, "run_id")
        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(sequence_number), 0) + 1
            FROM events
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return int(row[0])

    def get(self, event_id: str) -> sqlite3.Row | None:
        self.require_text(event_id, "event_id")
        return self._connection.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (event_id,),
        ).fetchone()

    def get_by_idempotency_key(
        self,
        run_id: str,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        self.require_text(run_id, "run_id")
        self.require_text(idempotency_key, "idempotency_key")
        return self._connection.execute(
            """
            SELECT * FROM events
            WHERE run_id = ? AND idempotency_key = ?
            """,
            (run_id, idempotency_key),
        ).fetchone()

    def create_event(
        self,
        *,
        event_id: str,
        run_id: str,
        sequence_number: int,
        event_type: str,
        actor: str,
        payload: Mapping[str, object],
        extraction_method: str,
        event_status: str,
        idempotency_key: str,
        created_at: str,
        session_id: str | None = None,
        extractor_version: str | None = None,
        validated_at: str | None = None,
    ) -> str:
        for name, value in (
            ("event_id", event_id),
            ("run_id", run_id),
            ("event_type", event_type),
            ("actor", actor),
            ("idempotency_key", idempotency_key),
            ("created_at", created_at),
        ):
            require_text(value, name)

        if isinstance(sequence_number, bool) or not isinstance(sequence_number, int) or sequence_number < 1:
            raise ValueError("Event sequence number must be positive.")

        if extraction_method not in EVENT_METHODS:
            raise ValueError("Invalid event extraction method.")

        if event_status not in EVENT_STATUSES:
            raise ValueError("Invalid event status.")

        serialized_payload = json_text(payload, "payload")

        existing = self.get_by_idempotency_key(run_id, idempotency_key)
        if existing is not None:
            expected = (
                existing["event_type"],
                existing["actor"],
                existing["payload"],
                existing["session_id"],
            )
            supplied = (event_type, actor, serialized_payload, session_id)
            if expected == supplied:
                return existing["event_id"]
            raise ValueError("Event idempotency key was reused with different data.")

        if session_id is not None:
            require_session_for_run(self._connection, session_id, run_id)

        self._connection.execute(
            """
            INSERT INTO events (
                event_id, run_id, session_id, sequence_number,
                event_type, actor, payload, extraction_method,
                extractor_version, event_status, idempotency_key,
                created_at, validated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                run_id,
                session_id,
                sequence_number,
                event_type,
                actor,
                serialized_payload,
                extraction_method,
                extractor_version,
                event_status,
                idempotency_key,
                created_at,
                validated_at,
            ),
        )
        return event_id

    def add_evidence(
        self,
        *,
        event_id: str,
        message_id: str,
        evidence_type: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
        annotation: str | None = None,
    ) -> bool:
        require_text(event_id, "event_id")
        require_text(message_id, "message_id")
        require_text(evidence_type, "evidence_type")

        event = self.get(event_id)
        if event is None:
            raise ValueError("Event does not exist.")

        message = require_message_for_run(
            self._connection,
            message_id,
            event["run_id"],
        )

        if event["session_id"] is not None and event["session_id"] != message["session_id"]:
            raise ValueError("Evidence message belongs to another session.")

        require_offsets(message["content"], start_offset, end_offset)

        previous = self._connection.execute(
            """
            SELECT * FROM event_evidence
            WHERE event_id = ? AND message_id = ? AND evidence_type = ?
            """,
            (event_id, message_id, evidence_type),
        ).fetchone()

        if previous is not None:
            expected = (
                previous["start_offset"],
                previous["end_offset"],
                previous["annotation"],
            )
            supplied = (start_offset, end_offset, annotation)
            if expected == supplied:
                return False
            raise ValueError("Event evidence identity already exists with different data.")

        self._connection.execute(
            """
            INSERT INTO event_evidence (
                event_id, message_id, evidence_type,
                start_offset, end_offset, annotation
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                message_id,
                evidence_type,
                start_offset,
                end_offset,
                annotation,
            ),
        )
        return True

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM events
                WHERE run_id = ?
                ORDER BY sequence_number
                """,
                (run_id,),
            ).fetchall()
        )

    def list_evidence(self, event_id: str) -> list[sqlite3.Row]:
        self.require_text(event_id, "event_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM event_evidence
                WHERE event_id = ?
                ORDER BY message_id, evidence_type
                """,
                (event_id,),
            ).fetchall()
        )
