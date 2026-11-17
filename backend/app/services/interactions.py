"""Transactional orchestration for idempotent Patient Agent interactions."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.llm.client import ProviderConnectionError, ProviderResponseError
from app.llm.patient_agent import (
    PatientAgent,
    PatientAgentIncompleteResponseError,
    PatientAgentOutputValidationError,
)
from app.llm.patient_agent_output import PATIENT_AGENT_OUTPUT_SCHEMA_VERSION
from app.llm.patient_agent_prompt import (
    PATIENT_AGENT_PROMPT_ID,
    PATIENT_AGENT_PROMPT_VERSION,
)
from app.llm.patient_context_serializer import (
    PATIENT_AGENT_CONTEXT_SCHEMA_VERSION,
    patient_context_to_payload,
)
from app.persistence.database import DatabaseManager
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.memory_extraction_jobs import (
    MemoryExtractionJobRepository,
)
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import (
    AuditRepository,
    ModelRunRepository,
)
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.services.patient_context import PatientContext
from app.services.patient_context_service import (
    PatientContextService,
    PatientContextServiceError,
)


class InteractionServiceError(RuntimeError):
    """Base error for interaction orchestration."""


class InteractionSessionNotFoundError(InteractionServiceError):
    """The requested session does not exist."""


class InteractionSessionNotActiveError(InteractionServiceError):
    """The requested session is not active."""


class InteractionRunNotActiveError(InteractionServiceError):
    """The simulation run is not active."""


class InteractionIdempotencyConflictError(InteractionServiceError):
    """An idempotency key was reused with a different request payload."""


class InteractionSessionBusyError(InteractionServiceError):
    """Another unresolved interaction blocks a new request in this session."""


class InteractionPersistenceIntegrityError(InteractionServiceError):
    """Persisted interaction data is incomplete or inconsistent."""


class InteractionAttemptOwnershipLostError(InteractionServiceError):
    """The current worker no longer owns a live interaction attempt."""


class InteractionGenerationError(InteractionServiceError):
    """Patient generation failed; only a sanitized error code is exposed."""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(f"Patient generation failed: {error_code}.")


@dataclass(frozen=True, slots=True)
class InteractionRecord:
    """Public interaction result; no restricted case context is exposed."""

    status: str
    session_id: str
    request_id: str
    attempt_number: int
    therapist_message_id: str
    therapist_content: str
    patient_message_id: str | None = None
    patient_content: str | None = None


@dataclass(frozen=True, slots=True)
class _Attempt:
    request_id: str
    run_id: str
    session_id: str
    therapist_message_id: str
    attempt_token: str
    model_run_id: str
    attempt_number: int


class InteractionService:
    """Own interaction persistence while keeping inference outside transactions."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        patient_agent: PatientAgent,
        patient_context_service: PatientContextService | None = None,
        *,
        request_timeout_seconds: float = 120.0,
        lease_grace_seconds: float = 30.0,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("database_manager must be a DatabaseManager.")

        if not isinstance(patient_agent, PatientAgent):
            raise TypeError("patient_agent must be a PatientAgent.")

        if (
            isinstance(request_timeout_seconds, bool)
            or not isinstance(request_timeout_seconds, (int, float))
            or not math.isfinite(request_timeout_seconds)
            or not 1 <= request_timeout_seconds <= 600
        ):
            raise ValueError(
                "request_timeout_seconds must be between 1 and 600."
            )

        if (
            isinstance(lease_grace_seconds, bool)
            or not isinstance(lease_grace_seconds, (int, float))
            or not math.isfinite(lease_grace_seconds)
            or lease_grace_seconds < 0
        ):
            raise ValueError("lease_grace_seconds must be non-negative.")

        self.database_manager = database_manager
        self.patient_agent = patient_agent
        self.patient_context_service = (
            patient_context_service
            if patient_context_service is not None
            else PatientContextService(database_manager)
        )
        self.request_timeout_seconds = float(request_timeout_seconds)
        self.lease_grace_seconds = float(lease_grace_seconds)
        self.lease_seconds = (
            self.request_timeout_seconds + self.lease_grace_seconds
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    @staticmethod
    def _require_text(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value

    @staticmethod
    def _format_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _now(self) -> datetime:
        value = self.clock()

        if not isinstance(value, datetime):
            raise TypeError("clock must return a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("clock must return an aware UTC datetime.")

        return value.astimezone(timezone.utc)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise InteractionPersistenceIntegrityError(
                "A persisted timestamp is missing."
            )

        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            raise InteractionPersistenceIntegrityError(
                "A persisted timestamp is invalid."
            ) from None

        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise InteractionPersistenceIntegrityError(
                "A persisted timestamp is not UTC."
            )

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _digest_json(payload: object) -> str:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _digest_text(value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _new_id(self, prefix: str) -> str:
        value = self.id_factory()

        if not isinstance(value, str) or not value.strip():
            raise ValueError("id_factory must return a non-empty string.")

        return f"{prefix}-{value}"

    def _ensure_active_session_and_run(
        self,
        connection,
        session,
    ) -> str:
        if session["status"] != "active":
            raise InteractionSessionNotActiveError(
                "The requested session is not active."
            )

        run = SimulationRunRepository(connection).get_run(session["run_id"])

        if run is None:
            raise InteractionPersistenceIntegrityError(
                "The session references a missing simulation run."
            )

        if run["status"] != "active":
            raise InteractionRunNotActiveError(
                "The simulation run is not active."
            )

        return run["run_id"]

    def _request_has_live_lease(
        self,
        request,
        now: datetime,
    ) -> bool:
        if request["processing_status"] != "in_progress":
            return False

        if not request["attempt_token"] or not request["lease_expires_at"]:
            return False

        return self._parse_utc(request["lease_expires_at"]) > now

    def _load_therapist_message(
        self,
        messages: MessageRepository,
        request,
    ):
        message_id = request["therapist_message_id"]

        if not message_id:
            raise InteractionPersistenceIntegrityError(
                "The interaction request has no persisted therapist message."
            )

        message = messages.get_message(message_id)

        if (
            message is None
            or message["role"] != "therapist"
            or message["session_id"] != request["session_id"]
        ):
            raise InteractionPersistenceIntegrityError(
                "The persisted therapist message is inconsistent."
            )

        return message

    def _completed_record(
        self,
        messages: MessageRepository,
        request,
    ) -> InteractionRecord:
        therapist = self._load_therapist_message(messages, request)
        patient_id = request["patient_message_id"]

        if not patient_id:
            raise InteractionPersistenceIntegrityError(
                "A completed request has no patient response identifier."
            )

        patient = messages.get_message(patient_id)

        if (
            patient is None
            or patient["role"] != "patient"
            or patient["session_id"] != request["session_id"]
        ):
            raise InteractionPersistenceIntegrityError(
                "The persisted patient response is inconsistent."
            )

        return InteractionRecord(
            status="completed",
            session_id=request["session_id"],
            request_id=request["request_id"],
            attempt_number=request["attempt_number"],
            therapist_message_id=therapist["message_id"],
            therapist_content=therapist["content"],
            patient_message_id=patient["message_id"],
            patient_content=patient["content"],
        )

    def _processing_record(
        self,
        messages: MessageRepository,
        request,
    ) -> InteractionRecord:
        therapist = self._load_therapist_message(messages, request)

        return InteractionRecord(
            status="processing",
            session_id=request["session_id"],
            request_id=request["request_id"],
            attempt_number=request["attempt_number"],
            therapist_message_id=therapist["message_id"],
            therapist_content=therapist["content"],
        )

    def _record_audit(
        self,
        connection,
        *,
        request_id: str,
        run_id: str,
        session_id: str,
        operation_type: str,
        operation_status: str,
        created_at: str,
        metadata: dict[str, object],
    ) -> None:
        AuditRepository(connection).record(
            audit_event_id=self._new_id("audit"),
            component="orchestrator",
            operation_type=operation_type,
            entity_type="interaction_request",
            entity_id=request_id,
            run_id=run_id,
            session_id=session_id,
            operation_status=operation_status,
            metadata=metadata,
            created_at=created_at,
        )

    def _start_attempt(
        self,
        connection,
        *,
        request,
        run_id: str,
        session_id: str,
        therapist_message_id: str,
        now: datetime,
    ) -> _Attempt:
        requests = InteractionRequestRepository(connection)
        models = ModelRunRepository(connection)
        now_text = self._format_utc(now)

        previous_model_run_id = request["last_model_run_id"]

        if previous_model_run_id:
            previous_model = models.get(previous_model_run_id)

            if (
                previous_model is not None
                and previous_model["execution_status"] == "in_progress"
            ):
                models.fail(
                    previous_model_run_id,
                    completed_at=now_text,
                    output_validation_status="not_validated",
                )

        model_run_id = self._new_id("model-run")
        attempt_token = self._new_id("attempt")
        provider_config = self.patient_agent.client.config

        models.create_model_run(
            model_run_id=model_run_id,
            run_id=run_id,
            session_id=session_id,
            component="patient_agent",
            provider=provider_config.name,
            model_identifier=self.patient_agent.model,
            execution_status="in_progress",
            started_at=now_text,
            generation_parameters={
                "temperature": self.patient_agent.temperature,
                "max_tokens": self.patient_agent.max_tokens,
            },
            prompt_id=PATIENT_AGENT_PROMPT_ID,
            prompt_version=PATIENT_AGENT_PROMPT_VERSION,
            input_schema_version=PATIENT_AGENT_CONTEXT_SCHEMA_VERSION,
            output_schema_version=PATIENT_AGENT_OUTPUT_SCHEMA_VERSION,
        )

        lease_expires_at = self._format_utc(
            now + timedelta(seconds=self.lease_seconds)
        )

        claimed = requests.claim_attempt(
            request["request_id"],
            attempt_token,
            now=now_text,
            lease_expires_at=lease_expires_at,
            model_run_id=model_run_id,
        )

        if not claimed:
            raise InteractionSessionBusyError(
                "The interaction attempt could not be claimed."
            )

        current = requests.get_request(request["request_id"])

        self._record_audit(
            connection,
            request_id=request["request_id"],
            run_id=run_id,
            session_id=session_id,
            operation_type="interaction_attempt_started",
            operation_status="success",
            created_at=now_text,
            metadata={
                "attempt_number": current["attempt_number"],
                "model_run_id": model_run_id,
            },
        )

        return _Attempt(
            request_id=request["request_id"],
            run_id=run_id,
            session_id=session_id,
            therapist_message_id=therapist_message_id,
            attempt_token=attempt_token,
            model_run_id=model_run_id,
            attempt_number=current["attempt_number"],
        )

    def handle_message(
        self,
        session_id: str,
        idempotency_key: str,
        content: str,
    ) -> InteractionRecord:
        """Persist therapist input, invoke the Patient Agent, and persist output."""

        self._require_text(session_id, "session_id")
        self._require_text(idempotency_key, "idempotency_key")
        self._require_text(content, "content")

        request_hash = self._digest_json({"content": content})
        now = self._now()
        now_text = self._format_utc(now)

        with self.database_manager.transaction("operational") as connection:
            sessions = SessionRepository(connection)
            session = sessions.get_session(session_id)

            if session is None:
                raise InteractionSessionNotFoundError(
                    "The requested session does not exist."
                )

            requests = InteractionRequestRepository(connection)
            messages = MessageRepository(connection)

            existing = requests.get_by_idempotency_key(
                session_id,
                idempotency_key,
            )

            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise InteractionIdempotencyConflictError(
                        "The idempotency key was already used with another payload."
                    )

                if existing["processing_status"] == "completed":
                    return self._completed_record(messages, existing)

            run_id = self._ensure_active_session_and_run(
                connection,
                session,
            )

            if existing is not None:
                therapist = self._load_therapist_message(
                    messages,
                    existing,
                )

                if therapist["content"] != content:
                    raise InteractionPersistenceIntegrityError(
                        "The persisted therapist message does not match its request hash."
                    )

                if self._request_has_live_lease(existing, now):
                    return self._processing_record(messages, existing)

                attempt = self._start_attempt(
                    connection,
                    request=existing,
                    run_id=run_id,
                    session_id=session_id,
                    therapist_message_id=therapist["message_id"],
                    now=now,
                )

            else:
                if requests.count_unresolved_by_session(session_id) > 0:
                    raise InteractionSessionBusyError(
                        "This session has an unresolved interaction request."
                    )

                request_id = self._new_id("request")
                therapist_message_id = self._new_id("message")

                requests.create_request(
                    request_id=request_id,
                    session_id=session_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    created_at=now_text,
                )

                messages.create_message(
                    message_id=therapist_message_id,
                    session_id=session_id,
                    sequence_number=messages.next_sequence_number(session_id),
                    role="therapist",
                    content=content,
                    created_at=now_text,
                    content_hash=self._digest_text(content),
                )

                requests.attach_therapist_message(
                    request_id,
                    therapist_message_id,
                )

                created_request = requests.get_request(request_id)

                attempt = self._start_attempt(
                    connection,
                    request=created_request,
                    run_id=run_id,
                    session_id=session_id,
                    therapist_message_id=therapist_message_id,
                    now=now,
                )

        return self._execute_attempt(attempt)

    def _execute_attempt(
        self,
        attempt: _Attempt,
    ) -> InteractionRecord:
        try:
            context = self.patient_context_service.build_patient_context(
                attempt.run_id,
                attempt.session_id,
                attempt.therapist_message_id,
            )

            if not isinstance(context, PatientContext):
                raise TypeError(
                    "PatientContextService returned an invalid context."
                )

            if (
                context.run_id != attempt.run_id
                or context.session_id != attempt.session_id
                or context.therapist_message.message_id
                != attempt.therapist_message_id
            ):
                raise InteractionPersistenceIntegrityError(
                    "Patient context does not match the active interaction."
                )

            # Mirror the exact JSON envelope sent by PatientAgent._build_messages.
            input_payload = {
                "patient_context": patient_context_to_payload(context)
            }
            input_hash = self._digest_json(input_payload)

            with self.database_manager.transaction("operational") as connection:
                requests = InteractionRequestRepository(connection)
                models = ModelRunRepository(connection)

                try:
                    requests.assert_attempt_owned(
                        attempt.request_id,
                        attempt.attempt_token,
                        now=self._format_utc(self._now()),
                        model_run_id=attempt.model_run_id,
                    )
                except ValueError:
                    raise InteractionAttemptOwnershipLostError(
                        "The interaction attempt is no longer owned by this worker."
                    ) from None

                if not models.set_input_hash(
                    attempt.model_run_id,
                    input_hash,
                ):
                    raise InteractionAttemptOwnershipLostError(
                        "The model run no longer accepts an input hash."
                    )

            # No SQLite transaction is open while the local model is running.
            result = self.patient_agent.generate_response(context)
            patient_content = result.output.content

            if not isinstance(patient_content, str) or not patient_content.strip():
                raise PatientAgentOutputValidationError(
                    "Patient Agent returned empty content."
                )

            return self._complete_attempt(
                attempt,
                patient_content,
                result,
            )

        except InteractionAttemptOwnershipLostError:
            self._record_attempt_failure(
                attempt,
                "attempt_ownership_lost",
            )
            raise
        except Exception as exc:
            error_code = self._sanitize_error_code(exc)
            self._record_attempt_failure(attempt, error_code)
            raise InteractionGenerationError(error_code) from None

    @staticmethod
    def _sanitize_error_code(error: Exception) -> str:
        if isinstance(error, ProviderConnectionError):
            return "provider_unavailable"

        if isinstance(error, ProviderResponseError):
            return "provider_error"

        if isinstance(error, PatientAgentIncompleteResponseError):
            return "incomplete_model_response"

        if isinstance(error, PatientAgentOutputValidationError):
            return "invalid_agent_output"

        if isinstance(error, PatientContextServiceError):
            return "patient_context_error"

        if isinstance(error, TimeoutError):
            return "provider_timeout"

        return "interaction_failed"

    def _complete_attempt(
        self,
        attempt: _Attempt,
        patient_content: str,
        result,
    ) -> InteractionRecord:
        completed_at = self._format_utc(self._now())
        patient_message_id = self._new_id("message")
        content_hash = self._digest_text(patient_content)

        with self.database_manager.transaction("operational") as connection:
            requests = InteractionRequestRepository(connection)
            models = ModelRunRepository(connection)
            messages = MessageRepository(connection)

            try:
                requests.assert_attempt_owned(
                    attempt.request_id,
                    attempt.attempt_token,
                    now=completed_at,
                    model_run_id=attempt.model_run_id,
                )
            except ValueError:
                raise InteractionAttemptOwnershipLostError(
                    "The interaction attempt is no longer owned by this worker."
                ) from None

            if not models.complete(
                attempt.model_run_id,
                completed_at=completed_at,
                output_hash=content_hash,
                output_validation_status="valid",
            ):
                raise InteractionAttemptOwnershipLostError(
                    "The model run is no longer active."
                )

            messages.create_message(
                message_id=patient_message_id,
                session_id=attempt.session_id,
                sequence_number=messages.next_sequence_number(
                    attempt.session_id
                ),
                role="patient",
                content=patient_content,
                created_at=completed_at,
                model_run_id=attempt.model_run_id,
                content_hash=content_hash,
            )

            events = EventRepository(connection)
            event_sequence = events.next_sequence_number(attempt.run_id)
            for offset, (event_type, actor, message_id) in enumerate(
                (
                    (
                        "therapist_message_received",
                        "therapist",
                        attempt.therapist_message_id,
                    ),
                    (
                        "patient_response_generated",
                        "patient",
                        patient_message_id,
                    ),
                )
            ):
                event_id = events.create_event(
                    event_id=self._new_id("event"),
                    run_id=attempt.run_id,
                    session_id=attempt.session_id,
                    sequence_number=event_sequence + offset,
                    event_type=event_type,
                    actor=actor,
                    payload={
                        "interaction_request_id": attempt.request_id,
                        "message_id": message_id,
                    },
                    extraction_method="application_rule",
                    extractor_version="interaction-persistence-v1",
                    event_status="accepted",
                    idempotency_key=(
                        f"interaction:{attempt.request_id}:{actor}"
                    ),
                    created_at=completed_at,
                )
                events.add_evidence(
                    event_id=event_id,
                    message_id=message_id,
                    evidence_type="observed_message",
                )

            requests.mark_completed(
                attempt.request_id,
                patient_message_id,
                completed_at,
                attempt_token=attempt.attempt_token,
            )
            MemoryExtractionJobRepository(connection).enqueue(
                job_id=self._new_id("memory-extraction-job"),
                run_id=attempt.run_id,
                session_id=attempt.session_id,
                interaction_request_id=attempt.request_id,
                created_at=completed_at,
            )

            usage = (
                dict(result.usage)
                if result.usage is not None
                else None
            )

            self._record_audit(
                connection,
                request_id=attempt.request_id,
                run_id=attempt.run_id,
                session_id=attempt.session_id,
                operation_type="interaction_completed",
                operation_status="success",
                created_at=completed_at,
                metadata={
                    "attempt_number": attempt.attempt_number,
                    "model_run_id": attempt.model_run_id,
                    "reported_model_identifier": result.model_identifier,
                    "finish_reason": result.finish_reason,
                    "usage": usage,
                },
            )

            request = requests.get_request(attempt.request_id)
            therapist = messages.get_message(attempt.therapist_message_id)

            return InteractionRecord(
                status="completed",
                session_id=attempt.session_id,
                request_id=attempt.request_id,
                attempt_number=request["attempt_number"],
                therapist_message_id=therapist["message_id"],
                therapist_content=therapist["content"],
                patient_message_id=patient_message_id,
                patient_content=patient_content,
            )

    def _record_attempt_failure(
        self,
        attempt: _Attempt,
        error_code: str,
    ) -> None:
        failed_at = self._format_utc(self._now())

        with self.database_manager.transaction("operational") as connection:
            requests = InteractionRequestRepository(connection)
            models = ModelRunRepository(connection)

            owns_attempt = True

            try:
                requests.assert_attempt_owned(
                    attempt.request_id,
                    attempt.attempt_token,
                    now=failed_at,
                    model_run_id=attempt.model_run_id,
                )
            except ValueError:
                owns_attempt = False

            model = models.get(attempt.model_run_id)
            model_failed = False

            if (
                model is not None
                and model["execution_status"] == "in_progress"
            ):
                model_failed = models.fail(
                    attempt.model_run_id,
                    completed_at=failed_at,
                    output_validation_status="not_validated",
                )

            request_failed = False

            if owns_attempt and model_failed:
                requests.mark_failed(
                    attempt.request_id,
                    error_code,
                    attempt_token=attempt.attempt_token,
                    failed_at=failed_at,
                )
                request_failed = True

            self._record_audit(
                connection,
                request_id=attempt.request_id,
                run_id=attempt.run_id,
                session_id=attempt.session_id,
                operation_type=(
                    "interaction_attempt_failed"
                    if request_failed
                    else "interaction_attempt_abandoned"
                ),
                operation_status=(
                    "failed"
                    if request_failed
                    else "stale"
                ),
                created_at=failed_at,
                metadata={
                    "attempt_number": attempt.attempt_number,
                    "model_run_id": attempt.model_run_id,
                    "error_code": error_code,
                },
            )
