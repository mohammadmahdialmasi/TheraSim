"""Append-only review decisions for model-proposed behavioral events."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.events import EventRepository


class EventReviewError(RuntimeError):
    """Base error for event review operations."""


class EventReviewNotFoundError(EventReviewError):
    """The requested event does not exist in the requested Run."""


class EventReviewConflictError(EventReviewError):
    """The event was already reviewed or its state conflicts with review."""


class EventReviewIntegrityError(EventReviewError):
    """Persisted event data is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class EventEvidenceRecord:
    message_id: str
    role: str
    message_content: str
    start_offset: int | None
    end_offset: int | None
    annotation: str | None

    @property
    def excerpt(self) -> str | None:
        if self.start_offset is None or self.end_offset is None:
            return None
        return self.message_content[self.start_offset : self.end_offset]


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    run_id: str
    session_id: str | None
    sequence_number: int
    event_type: str
    actor: str
    payload: dict[str, object]
    extraction_method: str
    extractor_version: str | None
    event_status: str
    created_at: str
    validated_at: str | None
    evidence: tuple[EventEvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class EventReviewRecord:
    review_id: str
    event_id: str
    run_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


class EventReviewService:
    """Lists Run-scoped events and records one immutable review per event."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("database_manager must be a DatabaseManager.")
        self._database_manager = database_manager

    @staticmethod
    def _record_from_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> EventRecord:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            raise EventReviewIntegrityError(
                "Persisted event payload is invalid JSON."
            ) from None
        if not isinstance(payload, dict):
            raise EventReviewIntegrityError(
                "Persisted event payload must be a JSON object."
            )
        evidence_rows = connection.execute(
            """
            SELECT e.message_id, m.role, m.content, e.start_offset,
                   e.end_offset, e.annotation
            FROM event_evidence AS e
            JOIN messages AS m ON m.message_id = e.message_id
            WHERE e.event_id = ?
            ORDER BY m.sequence_number, e.evidence_type
            """,
            (row["event_id"],),
        ).fetchall()
        evidence = tuple(
            EventEvidenceRecord(
                message_id=item["message_id"],
                role=item["role"],
                message_content=item["content"],
                start_offset=item["start_offset"],
                end_offset=item["end_offset"],
                annotation=item["annotation"],
            )
            for item in evidence_rows
        )
        return EventRecord(
            event_id=row["event_id"],
            run_id=row["run_id"],
            session_id=row["session_id"],
            sequence_number=row["sequence_number"],
            event_type=row["event_type"],
            actor=row["actor"],
            payload=payload,
            extraction_method=row["extraction_method"],
            extractor_version=row["extractor_version"],
            event_status=row["event_status"],
            created_at=row["created_at"],
            validated_at=row["validated_at"],
            evidence=evidence,
        )

    def list_events(
        self,
        run_id: str,
        *,
        status: str | None = None,
    ) -> list[EventRecord]:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be non-empty text.")
        if status is not None and status not in {
            "candidate",
            "accepted",
            "rejected",
            "requires_review",
        }:
            raise ValueError("status is not a valid event status.")
        with self._database_manager.connection("operational") as connection:
            rows = EventRepository(connection).list_by_run(run_id)
            return [
                self._record_from_row(connection, row)
                for row in rows
                if status is None or row["event_status"] == status
            ]

    def review_event(
        self,
        *,
        run_id: str,
        event_id: str,
        decision: str,
        reviewer_id: str,
        rationale: str,
        reviewed_at: str,
    ) -> tuple[EventRecord, EventReviewRecord]:
        for name, value in (
            ("run_id", run_id),
            ("event_id", event_id),
            ("reviewer_id", reviewer_id),
            ("rationale", rationale),
            ("reviewed_at", reviewed_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text.")
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected.")

        with self._database_manager.transaction("operational") as connection:
            repository = EventRepository(connection)
            event = repository.get(event_id)
            if event is None or event["run_id"] != run_id:
                raise EventReviewNotFoundError("Event does not exist.")
            existing = connection.execute(
                "SELECT * FROM event_reviews WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if existing is not None:
                same_decision = (
                    existing["run_id"] == run_id
                    and existing["decision"] == decision
                    and existing["reviewer_id"] == reviewer_id
                    and existing["rationale"] == rationale
                )
                if not same_decision:
                    raise EventReviewConflictError(
                        "The event already has a different immutable review."
                    )
                updated = repository.get(event_id)
                if updated is None:
                    raise EventReviewIntegrityError(
                        "Reviewed event could not be read."
                    )
                return (
                    self._record_from_row(connection, updated),
                    EventReviewRecord(
                        review_id=existing["review_id"],
                        event_id=existing["event_id"],
                        run_id=existing["run_id"],
                        decision=existing["decision"],
                        reviewer_id=existing["reviewer_id"],
                        rationale=existing["rationale"],
                        reviewed_at=existing["reviewed_at"],
                    ),
                )
            if event["event_status"] not in {"candidate", "requires_review"}:
                raise EventReviewConflictError(
                    "Only unreviewed candidate events can be reviewed."
                )

            review_id = f"event-review-{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO event_reviews (
                    review_id, event_id, run_id, decision, reviewer_id,
                    rationale, reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    event_id,
                    run_id,
                    decision,
                    reviewer_id,
                    rationale.strip(),
                    reviewed_at,
                ),
            )
            connection.execute(
                """
                UPDATE events
                SET event_status = ?, validated_at = ?
                WHERE event_id = ? AND run_id = ?
                """,
                (decision, reviewed_at, event_id, run_id),
            )
            updated = repository.get(event_id)
            if updated is None:
                raise EventReviewIntegrityError(
                    "Reviewed event could not be read."
                )
            return (
                self._record_from_row(connection, updated),
                EventReviewRecord(
                    review_id=review_id,
                    event_id=event_id,
                    run_id=run_id,
                    decision=decision,
                    reviewer_id=reviewer_id,
                    rationale=rationale.strip(),
                    reviewed_at=reviewed_at,
                ),
            )
