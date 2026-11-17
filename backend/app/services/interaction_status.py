"""Read-only public status access for persisted interactions."""

from dataclasses import dataclass

from app.persistence.database import DatabaseManager
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)


@dataclass(frozen=True, slots=True)
class InteractionRequestStatusRecord:
    request_id: str
    session_id: str
    processing_status: str
    therapist_message_id: str | None
    patient_message_id: str | None
    error_code: str | None
    created_at: str
    completed_at: str | None


class InteractionRequestStatusService:
    """Expose a restricted operational projection of interaction requests."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        self._database_manager = database_manager

    def get_request_status(
        self,
        request_id: str,
    ) -> InteractionRequestStatusRecord | None:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id must be a non-empty string.")

        with self._database_manager.connection("operational") as connection:
            row = InteractionRequestRepository(connection).get_request(
                request_id
            )

            if row is None:
                return None

            # Never return idempotency keys, payload hashes, attempt tokens,
            # lease timestamps, or internal model-run identifiers.
            return InteractionRequestStatusRecord(
                request_id=row["request_id"],
                session_id=row["session_id"],
                processing_status=row["processing_status"],
                therapist_message_id=row["therapist_message_id"],
                patient_message_id=row["patient_message_id"],
                error_code=row["error_code"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )
