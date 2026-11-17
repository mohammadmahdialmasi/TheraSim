"""Application service for sequential session lifecycle management."""

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.sessions import (
    SessionOrderError,
    SessionRepository,
)
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)


class SessionServiceError(Exception):
    """Base exception for session application operations."""


class SessionRunNotFoundError(SessionServiceError):
    """The parent simulation run does not exist."""


class SessionRunNotActiveError(SessionServiceError):
    """The parent simulation run does not permit this operation."""


class SessionNotFoundError(SessionServiceError):
    """The requested session does not exist."""


class SessionOrderViolationError(SessionServiceError):
    """The requested session violates sequential progression."""


class SessionTransitionError(SessionServiceError):
    """The requested session status transition is not permitted."""


class SessionHasUnresolvedInteractionsError(SessionServiceError):
    """The session contains unresolved interaction requests."""

    def __init__(self, unresolved_count: int) -> None:
        self.unresolved_count = unresolved_count
        super().__init__(
            f"Session has {unresolved_count} unresolved interaction request(s)."
        )


class SessionInvalidCompletionReasonError(SessionServiceError):
    """The supplied session completion reason is not supported."""

class SessionConflictError(SessionServiceError):
    """A session or audit identity conflicts with persisted data."""


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    run_id: str
    session_number: int
    status: str
    transcript_version: int
    started_at: str | None
    ended_at: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class SessionMessageRecord:
    message_id: str
    sequence_number: int
    role: str
    content: str
    created_at: str

class SessionService:
    """Coordinates sequential session creation and lifecycle transitions.

    The service owns operational database transactions.
    It never gives database connections or repository objects to agents.
    """

    _ALLOWED_TRANSITIONS = {
        "initialized": frozenset({"active", "failed"}),
        "active": frozenset({"completed", "interrupted", "failed"}),
        "interrupted": frozenset({"active", "failed"}),
        "completed": frozenset(),
        "failed": frozenset(),
    }

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        self._database_manager = database_manager

    @staticmethod
    def _from_row(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            session_id=row["session_id"],
            run_id=row["run_id"],
            session_number=row["session_number"],
            status=row["status"],
            transcript_version=row["transcript_version"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _calculate_transcript_hash(
        repository: MessageRepository,
        session_id: str,
    ) -> str:
        """Hash the ordered therapist-visible transcript deterministically."""

        digest = hashlib.sha256()
        digest.update(b"[")
        first = True
        offset = 0
        page_size = 200

        while True:
            rows = repository.list_by_session(
                session_id,
                limit=page_size,
                offset=offset,
            )

            for row in rows:
                item = {
                    "message_id": row["message_id"],
                    "sequence_number": row["sequence_number"],
                    "role": row["role"],
                    "content": row["content"],
                    "created_at": row["created_at"],
                }

                if not first:
                    digest.update(b",")

                encoded = json.dumps(
                    item,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")

                digest.update(encoded)
                first = False

            offset += len(rows)

            if len(rows) < page_size:
                break

        digest.update(b"]")
        return digest.hexdigest()
    @staticmethod
    def _record_audit(
        repository: AuditRepository,
        *,
        run_id: str,
        session_id: str,
        operation_type: str,
        occurred_at: str,
        metadata: dict[str, object],
    ) -> None:
        repository.record(
            audit_event_id=uuid.uuid4().hex,
            component="session_service",
            operation_type=operation_type,
            entity_type="session",
            entity_id=session_id,
            run_id=run_id,
            session_id=session_id,
            operation_status="succeeded",
            metadata=metadata,
            created_at=occurred_at,
        )

    def create_next_session(
        self,
        *,
        session_id: str,
        run_id: str,
        created_at: str,
        started_at: str | None = None,
    ) -> SessionRecord:
        """Create the next active session in a currently active run."""

        effective_started_at = started_at or created_at

        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                runs = SimulationRunRepository(connection)
                run = runs.get_run(run_id)

                if run is None:
                    raise SessionRunNotFoundError(
                        "The parent simulation run does not exist."
                    )

                if run["status"] != "active":
                    raise SessionRunNotActiveError(
                        "A session can only be created in an active run."
                    )

                sessions = SessionRepository(connection)

                session_number = sessions.create_next_session(
                    session_id=session_id,
                    run_id=run_id,
                    created_at=created_at,
                    status="active",
                    started_at=effective_started_at,
                )

                row = sessions.get_session(session_id)

                if row is None:
                    raise SessionServiceError(
                        "Created session could not be retrieved."
                    )

                self._record_audit(
                    AuditRepository(connection),
                    run_id=run_id,
                    session_id=session_id,
                    operation_type="session_created",
                    occurred_at=created_at,
                    metadata={
                        "session_number": session_number,
                        "initial_status": "active",
                    },
                )

                result = self._from_row(row)

        except SessionOrderError as exc:
            raise SessionOrderViolationError(str(exc)) from exc

        except sqlite3.IntegrityError as exc:
            raise SessionConflictError(
                "The session identifier or session number conflicts with existing data."
            ) from exc

        return result

    def get_session(
        self,
        session_id: str,
    ) -> SessionRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = SessionRepository(connection).get_session(session_id)

            return (
                self._from_row(row)
                if row is not None
                else None
            )

    def list_sessions(
        self,
        run_id: str,
    ) -> list[SessionRecord]:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            rows = SessionRepository(connection).list_by_run(run_id)

            return [
                self._from_row(row)
                for row in rows
            ]

    def list_messages(
        self,
        session_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[SessionMessageRecord], int]:
        """Return a paginated therapist-visible transcript."""

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 200
        ):
            raise ValueError("Limit must be between 1 and 200.")

        if (
            isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
        ):
            raise ValueError("Offset must be a non-negative integer.")

        with self._database_manager.connection(
            "operational"
        ) as connection:
            if SessionRepository(connection).get_session(session_id) is None:
                raise SessionNotFoundError(
                    "The requested session does not exist."
                )

            repository = MessageRepository(connection)
            total = repository.count_by_session(session_id)
            rows = repository.list_by_session(
                session_id,
                limit=limit,
                offset=offset,
            )

            messages = [
                SessionMessageRecord(
                    message_id=row["message_id"],
                    sequence_number=row["sequence_number"],
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

            return messages, total
    def _transition(
        self,
        session_id: str,
        *,
        target_status: str,
        occurred_at: str,
        operation_type: str,
    ) -> SessionRecord:
        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                sessions = SessionRepository(connection)
                session = sessions.get_session(session_id)

                if session is None:
                    raise SessionNotFoundError(
                        "The requested session does not exist."
                    )

                run = SimulationRunRepository(connection).get_run(
                    session["run_id"]
                )

                if run is None:
                    raise SessionRunNotFoundError(
                        "The parent simulation run does not exist."
                    )

                previous_status = session["status"]

                if target_status not in self._ALLOWED_TRANSITIONS.get(
                    previous_status,
                    frozenset(),
                ):
                    raise SessionTransitionError(
                        f"Cannot transition session from "
                        f"{previous_status} to {target_status}."
                    )

                if target_status in {
                    "active",
                    "completed",
                    "interrupted",
                } and run["status"] != "active":
                    raise SessionRunNotActiveError(
                        "The parent simulation run must be active."
                    )

                if target_status == "failed" and run["status"] == "completed":
                    raise SessionTransitionError(
                        "A session cannot fail after its run is completed."
                    )

                if target_status == "completed":
                    unresolved_count = (
                        InteractionRequestRepository(
                            connection
                        ).count_unresolved_by_session(session_id)
                    )

                    if unresolved_count:
                        raise SessionHasUnresolvedInteractionsError(
                            unresolved_count
                        )

                update_options: dict[str, str] = {}

                if target_status in {"completed", "failed"}:
                    update_options["ended_at"] = occurred_at

                updated = sessions.update_status(
                    session_id,
                    target_status,
                    **update_options,
                )

                if not updated:
                    raise SessionServiceError(
                        "Session status could not be updated."
                    )

                self._record_audit(
                    AuditRepository(connection),
                    run_id=session["run_id"],
                    session_id=session_id,
                    operation_type=operation_type,
                    occurred_at=occurred_at,
                    metadata={
                        "previous_status": previous_status,
                        "new_status": target_status,
                    },
                )

                updated_row = sessions.get_session(session_id)

                if updated_row is None:
                    raise SessionServiceError(
                        "Updated session could not be retrieved."
                    )

                result = self._from_row(updated_row)

        except sqlite3.IntegrityError as exc:
            raise SessionConflictError(
                "The session update conflicts with persisted data."
            ) from exc

        return result

    def complete_session(
        self,
        session_id: str,
        *,
        completed_at: str,
        completion_reason: str = "normal",
    ) -> SessionRecord:
        """Complete a session, persist its transcript hash, and remain idempotent."""

        allowed_reasons = {
            "normal",
            "trainee_ended",
            "system_interrupted",
        }

        if completion_reason not in allowed_reasons:
            raise SessionInvalidCompletionReasonError(
                "The supplied completion reason is not supported."
            )

        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                sessions = SessionRepository(connection)
                session = sessions.get_session(session_id)

                if session is None:
                    raise SessionNotFoundError(
                        "The requested session does not exist."
                    )

                message_repository = MessageRepository(connection)

                # A completed session is terminal. Repeated requests return
                # its existing result and never create another audit event.
                if session["status"] == "completed":
                    calculated_hash = self._calculate_transcript_hash(
                        message_repository,
                        session_id,
                    )

                    stored_hash = session["transcript_hash"]

                    if stored_hash is not None:
                        if stored_hash != calculated_hash:
                            raise SessionConflictError(
                                "The stored transcript hash does not match "
                                "the completed transcript."
                            )
                    else:
                        # Backfill hashes for completed sessions created
                        # before transcript hashing was introduced.
                        updated = sessions.update_status(
                            session_id,
                            "completed",
                            transcript_hash=calculated_hash,
                        )

                        if not updated:
                            raise SessionServiceError(
                                "Transcript hash could not be stored."
                            )

                        session = sessions.get_session(session_id)

                        if session is None:
                            raise SessionServiceError(
                                "Completed session could not be retrieved."
                            )

                    result = self._from_row(session)

                else:
                    previous_status = session["status"]

                    if "completed" not in self._ALLOWED_TRANSITIONS.get(
                        previous_status,
                        frozenset(),
                    ):
                        raise SessionTransitionError(
                            f"Cannot transition session from "
                            f"{previous_status} to completed."
                        )

                    run = SimulationRunRepository(connection).get_run(
                        session["run_id"]
                    )

                    if run is None:
                        raise SessionRunNotFoundError(
                            "The parent simulation run does not exist."
                        )

                    if run["status"] != "active":
                        raise SessionRunNotActiveError(
                            "The parent simulation run must be active."
                        )

                    unresolved_count = (
                        InteractionRequestRepository(
                            connection
                        ).count_unresolved_by_session(session_id)
                    )

                    if unresolved_count:
                        raise SessionHasUnresolvedInteractionsError(
                            unresolved_count
                        )

                    transcript_hash = self._calculate_transcript_hash(
                        message_repository,
                        session_id,
                    )

                    updated = sessions.update_status(
                        session_id,
                        "completed",
                        ended_at=completed_at,
                        transcript_hash=transcript_hash,
                    )

                    if not updated:
                        raise SessionServiceError(
                            "Session status could not be updated."
                        )

                    self._record_audit(
                        AuditRepository(connection),
                        run_id=session["run_id"],
                        session_id=session_id,
                        operation_type="session_completed",
                        occurred_at=completed_at,
                        metadata={
                            "previous_status": previous_status,
                            "new_status": "completed",
                            "completion_reason": completion_reason,
                            "transcript_hash": transcript_hash,
                        },
                    )

                    updated_row = sessions.get_session(session_id)

                    if updated_row is None:
                        raise SessionServiceError(
                            "Completed session could not be retrieved."
                        )

                    result = self._from_row(updated_row)

        except sqlite3.IntegrityError as exc:
            raise SessionConflictError(
                "The session update conflicts with persisted data."
            ) from exc

        return result
    def interrupt_session(
        self,
        session_id: str,
        *,
        interrupted_at: str,
    ) -> SessionRecord:
        return self._transition(
            session_id,
            target_status="interrupted",
            occurred_at=interrupted_at,
            operation_type="session_interrupted",
        )

    def resume_session(
        self,
        session_id: str,
        *,
        resumed_at: str,
    ) -> SessionRecord:
        return self._transition(
            session_id,
            target_status="active",
            occurred_at=resumed_at,
            operation_type="session_resumed",
        )

    def fail_session(
        self,
        session_id: str,
        *,
        failed_at: str,
    ) -> SessionRecord:
        return self._transition(
            session_id,
            target_status="failed",
            occurred_at=failed_at,
            operation_type="session_failed",
        )
