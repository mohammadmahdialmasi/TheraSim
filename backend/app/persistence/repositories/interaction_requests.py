"""Repository for idempotent therapist-message operations."""

import sqlite3
from datetime import datetime, timedelta, timezone

from app.persistence.repositories.base import ConnectionBoundRepository


REQUEST_STATUSES = {"in_progress", "completed", "failed"}


class InteractionRequestRepository(ConnectionBoundRepository):
    """Persists interaction identity and fenced processing attempts.

    The caller owns all transaction boundaries. Attempt tokens prevent stale
    model executions from completing or failing a newer attempt.
    """

    @staticmethod
    def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
        ConnectionBoundRepository.require_text(value, field_name)

        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an ISO-8601 UTC timestamp."
            ) from exc

        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError(
                f"{field_name} must include a UTC timezone."
            )

        return parsed.astimezone(timezone.utc)

    def create_request(
        self,
        *,
        request_id: str,
        session_id: str,
        idempotency_key: str,
        request_hash: str,
        created_at: str,
    ) -> None:
        for name, value in (
            ("request_id", request_id),
            ("session_id", session_id),
            ("idempotency_key", idempotency_key),
            ("request_hash", request_hash),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        self._connection.execute(
            """
            INSERT INTO interaction_requests (
                request_id, session_id,
                idempotency_key, request_hash,
                processing_status, created_at
            )
            VALUES (?, ?, ?, ?, 'in_progress', ?)
            """,
            (
                request_id,
                session_id,
                idempotency_key,
                request_hash,
                created_at,
            ),
        )

    def get_request(self, request_id: str) -> sqlite3.Row | None:
        self.require_text(request_id, "request_id")

        return self._connection.execute(
            "SELECT * FROM interaction_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()

    def get_by_idempotency_key(
        self,
        session_id: str,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        self.require_text(session_id, "session_id")
        self.require_text(idempotency_key, "idempotency_key")

        return self._connection.execute(
            """
            SELECT * FROM interaction_requests
            WHERE session_id = ? AND idempotency_key = ?
            """,
            (session_id, idempotency_key),
        ).fetchone()

    def attach_therapist_message(
        self,
        request_id: str,
        message_id: str,
    ) -> None:
        self.require_text(request_id, "request_id")
        self.require_text(message_id, "message_id")

        request = self.get_request(request_id)
        if request is None:
            raise ValueError("Interaction request does not exist.")

        message = self._connection.execute(
            """
            SELECT message_id, session_id, role
            FROM messages
            WHERE message_id = ?
            """,
            (message_id,),
        ).fetchone()

        if message is None:
            raise ValueError("Therapist message does not exist.")

        if message["session_id"] != request["session_id"]:
            raise ValueError("Message belongs to a different session.")

        if message["role"] != "therapist":
            raise ValueError("Message role must be therapist.")

        current = request["therapist_message_id"]
        if current is not None and current != message_id:
            raise ValueError("A different therapist message is already attached.")

        if request["processing_status"] == "completed":
            raise ValueError("Completed interaction requests are immutable.")

        if current is None and request["attempt_number"] > 0:
            raise ValueError(
                "Therapist input cannot be attached after an attempt has started."
            )

        self._connection.execute(
            """
            UPDATE interaction_requests
            SET therapist_message_id = ?
            WHERE request_id = ?
            """,
            (message_id, request_id),
        )

    def claim_attempt(
        self,
        request_id: str,
        attempt_token: str,
        *,
        now: str,
        lease_expires_at: str,
        model_run_id: str | None = None,
    ) -> bool:
        """Claim a new attempt or recover an expired/failed request."""

        self.require_text(request_id, "request_id")
        self.require_text(attempt_token, "attempt_token")

        now_value = self._parse_utc_timestamp(now, "now")
        expiry_value = self._parse_utc_timestamp(
            lease_expires_at,
            "lease_expires_at",
        )

        if expiry_value <= now_value:
            raise ValueError("Attempt lease must expire after the claim time.")

        request = self.get_request(request_id)
        if request is None:
            raise ValueError("Interaction request does not exist.")

        if request["processing_status"] == "completed":
            return False

        if request["therapist_message_id"] is None:
            raise ValueError(
                "Therapist input must be attached before claiming an attempt."
            )

        previous_token = request["attempt_token"]
        if previous_token is not None and previous_token == attempt_token:
            raise ValueError("A new attempt requires a fresh attempt token.")

        if model_run_id is not None:
            self.require_text(model_run_id, "model_run_id")
            model_run = self._connection.execute(
                """
                SELECT
                    model_run_id,
                    session_id,
                    component,
                    execution_status
                FROM model_runs
                WHERE model_run_id = ?
                """,
                (model_run_id,),
            ).fetchone()

            if model_run is None:
                raise ValueError("Model run does not exist.")

            if model_run["session_id"] != request["session_id"]:
                raise ValueError("Model run belongs to a different session.")

            if model_run["component"] != "patient_agent":
                raise ValueError(
                    "Interaction attempts require a patient-agent model run."
                )

            if model_run["execution_status"] != "in_progress":
                raise ValueError(
                    "The patient-agent model run must be in_progress."
                )

        cursor = self._connection.execute(
            """
            UPDATE interaction_requests
            SET processing_status = 'in_progress',
                error_code = NULL,
                completed_at = NULL,
                attempt_token = ?,
                lease_expires_at = ?,
                attempt_number = attempt_number + 1,
                last_model_run_id = ?
            WHERE request_id = ?
              AND (
                    processing_status = 'failed'
                    OR (
                        processing_status = 'in_progress'
                        AND (
                            attempt_token IS NULL
                            OR lease_expires_at IS NULL
                            OR julianday(lease_expires_at) <= julianday(?)
                        )
                    )
              )
            """,
            (
                attempt_token,
                lease_expires_at,
                model_run_id,
                request_id,
                now,
            ),
        )

        return cursor.rowcount == 1

    def assert_attempt_owned(
        self,
        request_id: str,
        attempt_token: str,
        *,
        now: str,
        model_run_id: str,
    ) -> None:
        """Verify that a live attempt still owns the request and model run."""

        self.require_text(request_id, "request_id")
        self.require_text(attempt_token, "attempt_token")
        self.require_text(model_run_id, "model_run_id")
        now_value = self._parse_utc_timestamp(now, "now")

        request = self.get_request(request_id)
        if request is None:
            raise ValueError("Interaction request does not exist.")

        if request["processing_status"] != "in_progress":
            raise ValueError("Interaction attempt is not in progress.")

        if request["attempt_token"] != attempt_token:
            raise ValueError(
                "Attempt token does not own this interaction request."
            )

        if request["last_model_run_id"] != model_run_id:
            raise ValueError(
                "Model run does not own the current interaction attempt."
            )

        if request["lease_expires_at"] is None:
            raise ValueError("Interaction attempt has no active lease.")

        expiry_value = self._parse_utc_timestamp(
            request["lease_expires_at"],
            "lease_expires_at",
        )
        if expiry_value <= now_value:
            raise ValueError("Interaction attempt lease has expired.")

        model_run = self._connection.execute(
            """
            SELECT model_run_id, session_id, component, execution_status
            FROM model_runs
            WHERE model_run_id = ?
            """,
            (model_run_id,),
        ).fetchone()

        if model_run is None:
            raise ValueError("Model run does not exist.")

        if model_run["session_id"] != request["session_id"]:
            raise ValueError("Model run belongs to a different session.")

        if model_run["component"] != "patient_agent":
            raise ValueError(
                "Interaction attempts require a patient-agent model run."
            )

        if model_run["execution_status"] != "in_progress":
            raise ValueError(
                "The patient-agent model run must be in_progress."
            )

    def mark_completed(
        self,
        request_id: str,
        patient_message_id: str,
        completed_at: str,
        *,
        attempt_token: str,
    ) -> None:
        self.require_text(request_id, "request_id")
        self.require_text(patient_message_id, "patient_message_id")
        self.require_text(attempt_token, "attempt_token")
        completed_value = self._parse_utc_timestamp(
            completed_at,
            "completed_at",
        )

        request = self.get_request(request_id)
        if request is None:
            raise ValueError("Interaction request does not exist.")

        if request["therapist_message_id"] is None:
            raise ValueError(
                "A therapist message must be attached before completion."
            )

        if request["attempt_token"] != attempt_token:
            raise ValueError("Attempt token does not own this interaction request.")

        patient_message = self._connection.execute(
            """
            SELECT message_id, session_id, role, model_run_id
            FROM messages
            WHERE message_id = ?
            """,
            (patient_message_id,),
        ).fetchone()

        if patient_message is None:
            raise ValueError("Patient message does not exist.")

        if patient_message["session_id"] != request["session_id"]:
            raise ValueError("Patient message belongs to a different session.")

        if patient_message["role"] != "patient":
            raise ValueError("Response message role must be patient.")

        if request["last_model_run_id"] is not None:
            if patient_message["model_run_id"] != request["last_model_run_id"]:
                raise ValueError(
                    "Patient message must belong to the current model run."
                )

        if request["processing_status"] == "completed":
            if request["patient_message_id"] == patient_message_id:
                return
            raise ValueError("Completed interaction result is immutable.")

        if request["processing_status"] != "in_progress":
            raise ValueError("Interaction request cannot be completed.")

        if request["lease_expires_at"] is None:
            raise ValueError("Interaction attempt has no active lease.")

        expiry_value = self._parse_utc_timestamp(
            request["lease_expires_at"],
            "lease_expires_at",
        )
        if expiry_value <= completed_value:
            raise ValueError("Interaction attempt lease has expired.")

        cursor = self._connection.execute(
            """
            UPDATE interaction_requests
            SET patient_message_id = ?,
                processing_status = 'completed',
                error_code = NULL,
                completed_at = ?,
                lease_expires_at = NULL
            WHERE request_id = ?
              AND processing_status = 'in_progress'
              AND attempt_token = ?
              AND julianday(lease_expires_at) > julianday(?)
            """,
            (
                patient_message_id,
                completed_at,
                request_id,
                attempt_token,
                completed_at,
            ),
        )

        if cursor.rowcount != 1:
            raise ValueError("Interaction attempt ownership was lost.")

    def mark_failed(
        self,
        request_id: str,
        error_code: str,
        *,
        attempt_token: str,
        failed_at: str,
    ) -> None:
        self.require_text(request_id, "request_id")
        self.require_text(error_code, "error_code")
        self.require_text(attempt_token, "attempt_token")
        failed_value = self._parse_utc_timestamp(failed_at, "failed_at")

        request = self.get_request(request_id)
        if request is None:
            raise ValueError("Interaction request does not exist.")

        if request["attempt_token"] != attempt_token:
            raise ValueError("Attempt token does not own this interaction request.")

        if request["processing_status"] == "completed":
            raise ValueError("A completed request cannot be marked failed.")

        if request["processing_status"] == "failed":
            if request["error_code"] == error_code:
                return
            raise ValueError("A failed request cannot be changed by this attempt.")

        if request["processing_status"] != "in_progress":
            raise ValueError("Interaction request cannot be marked failed.")

        if request["lease_expires_at"] is None:
            raise ValueError("Interaction attempt has no active lease.")

        expiry_value = self._parse_utc_timestamp(
            request["lease_expires_at"],
            "lease_expires_at",
        )
        if expiry_value <= failed_value:
            raise ValueError("Interaction attempt lease has expired.")

        cursor = self._connection.execute(
            """
            UPDATE interaction_requests
            SET processing_status = 'failed',
                error_code = ?,
                completed_at = NULL,
                lease_expires_at = NULL
            WHERE request_id = ?
              AND processing_status = 'in_progress'
              AND attempt_token = ?
              AND julianday(lease_expires_at) > julianday(?)
            """,
            (
                error_code,
                request_id,
                attempt_token,
                failed_at,
            ),
        )

        if cursor.rowcount != 1:
            raise ValueError("Interaction attempt ownership was lost.")

    def count_unresolved_by_session(self, session_id: str) -> int:
        """Count requests that have not reached a completed result."""

        self.require_text(session_id, "session_id")

        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM interaction_requests
            WHERE session_id = ?
              AND processing_status IN ('in_progress', 'failed')
            """,
            (session_id,),
        ).fetchone()

        return int(row[0])
