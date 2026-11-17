"""Durable memory-extraction jobs and their local worker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import sqlite3
import threading
import uuid

from pydantic import ValidationError

from app.llm.client import ProviderConnectionError, ProviderResponseError
from app.llm.memory_extraction_agent import (
    MEMORY_EXTRACTION_PROMPT_ID,
    MEMORY_EXTRACTION_PROMPT_VERSION,
    MEMORY_EXTRACTION_INPUT_SCHEMA_VERSION,
    MEMORY_EXTRACTION_SCHEMA_VERSION,
    MemoryExtractionAgent,
    MemoryExtractionAgentError,
    MemoryExtractionOutput,
)
from app.persistence.database import DatabaseManager
from app.persistence.repositories.memory_extraction_jobs import (
    MemoryExtractionJobRepository,
)
from app.persistence.repositories.operations import (
    AuditRepository,
    ModelRunRepository,
)
from app.services.memory import (
    MemoryEvidenceValidationError,
    MemoryIdempotencyConflictError,
    MemoryRequestNotCompletedError,
    MemoryRequestNotFoundError,
    MemoryReviewConflictError,
    MemoryService,
)


LOGGER = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class MemoryExtractionJob:
    job_id: str
    run_id: str
    session_id: str
    interaction_request_id: str
    status: str
    attempt_count: int
    candidate_count: int
    last_error_code: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class MemoryExtractionStatusService:
    """Expose Run-scoped job status without coupling the API to worker state."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("database_manager must be a DatabaseManager.")
        self._database_manager = database_manager

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> MemoryExtractionJob:
        return MemoryExtractionJob(
            job_id=row["job_id"],
            run_id=row["run_id"],
            session_id=row["session_id"],
            interaction_request_id=row["interaction_request_id"],
            status=row["status"],
            attempt_count=row["attempt_count"],
            candidate_count=row["candidate_count"],
            last_error_code=row["last_error_code"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def get_job(
        self,
        run_id: str,
        interaction_request_id: str,
    ) -> MemoryExtractionJob | None:
        with self._database_manager.connection("operational") as connection:
            row = MemoryExtractionJobRepository(connection).get_by_interaction(
                interaction_request_id
            )
            if row is None or row["run_id"] != run_id:
                return None
            return self._job_from_row(row)


class MemoryExtractionWorker:
    """Lease durable extraction work and persist only evidence-validated candidates."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        memory_service: MemoryService,
        agent: MemoryExtractionAgent,
        *,
        request_timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.0,
        id_factory=None,
        clock=None,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("database_manager must be a DatabaseManager.")
        if not isinstance(memory_service, MemoryService):
            raise TypeError("memory_service must be a MemoryService.")
        if not isinstance(agent, MemoryExtractionAgent):
            raise TypeError("agent must be a MemoryExtractionAgent.")
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
            isinstance(poll_interval_seconds, bool)
            or not isinstance(poll_interval_seconds, (int, float))
            or not 0.05 <= poll_interval_seconds <= 60
        ):
            raise ValueError("poll_interval_seconds must be between 0.05 and 60.")
        self._database_manager = database_manager
        self._memory_service = memory_service
        self._agent = agent
        self._request_timeout_seconds = float(request_timeout_seconds)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._lease_seconds = self._request_timeout_seconds + 30.0
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._stop_requested = threading.Event()
        worker_token = self._id_factory()
        if not isinstance(worker_token, str) or not worker_token.strip():
            raise TypeError("id_factory must return non-empty text.")
        self._worker_id = f"memory-worker-{worker_token}"

    @staticmethod
    def _format_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00",
            "Z",
        )

    def _now(self) -> datetime:
        current = self._clock()
        if (
            not isinstance(current, datetime)
            or current.tzinfo is None
            or current.utcoffset() != timedelta(0)
        ):
            raise ValueError("clock must return an aware UTC datetime.")
        return current.astimezone(timezone.utc)

    @staticmethod
    def _digest_json(payload: object) -> str:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _digest_text(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _start_model_run(
        self,
        job: sqlite3.Row,
        *,
        input_messages: list[dict[str, str]],
    ) -> str:
        started_at = self._format_utc(self._now())
        model_run_id = f"model-run-memory-{uuid.uuid4().hex}"
        input_hash = self._digest_json(input_messages)
        config = self._agent.client.config
        with self._database_manager.transaction("operational") as connection:
            models = ModelRunRepository(connection)
            previous_model_run_id = job["model_run_id"]
            if previous_model_run_id is not None:
                previous = models.get(previous_model_run_id)
                if (
                    previous is not None
                    and previous["execution_status"] == "in_progress"
                ):
                    models.fail(
                        previous_model_run_id,
                        completed_at=started_at,
                    )
            models.create_model_run(
                model_run_id=model_run_id,
                run_id=job["run_id"],
                session_id=job["session_id"],
                component="memory_extraction_agent",
                provider=config.name,
                model_identifier=self._agent.model,
                execution_status="in_progress",
                started_at=started_at,
                generation_parameters={
                    "temperature": 0.0,
                    "max_tokens": self._agent.max_tokens,
                },
                prompt_id=MEMORY_EXTRACTION_PROMPT_ID,
                prompt_version=MEMORY_EXTRACTION_PROMPT_VERSION,
                input_schema_version=MEMORY_EXTRACTION_INPUT_SCHEMA_VERSION,
                output_schema_version=MEMORY_EXTRACTION_SCHEMA_VERSION,
                input_hash=input_hash,
            )
            if not MemoryExtractionJobRepository(connection).set_model_run(
                job["job_id"],
                worker_id=self._worker_id,
                model_run_id=model_run_id,
                updated_at=started_at,
            ):
                raise RuntimeError(
                    "Memory extraction job lease was lost before model execution."
                )
        return model_run_id

    def _claim(self) -> sqlite3.Row | None:
        now = self._now()
        now_text = self._format_utc(now)
        lease_expires = self._format_utc(
            now + timedelta(seconds=self._lease_seconds)
        )
        with self._database_manager.transaction("operational") as connection:
            return MemoryExtractionJobRepository(connection).claim_next(
                worker_id=self._worker_id,
                now=now_text,
                lease_expires_at=lease_expires,
                max_attempts=MAX_ATTEMPTS,
            )

    def _load_transcript(
        self,
        *,
        interaction_request_id: str,
        session_id: str,
    ) -> list[dict[str, str]]:
        with self._database_manager.connection("operational") as connection:
            interaction = connection.execute(
                """
                SELECT r.processing_status, r.therapist_message_id,
                       r.patient_message_id, patient.sequence_number,
                       patient.session_id
                FROM interaction_requests AS r
                JOIN messages AS therapist
                  ON therapist.message_id = r.therapist_message_id
                JOIN messages AS patient
                  ON patient.message_id = r.patient_message_id
                WHERE r.request_id = ? AND r.session_id = ?
                  AND therapist.session_id = r.session_id
                  AND therapist.role = 'therapist'
                  AND patient.session_id = r.session_id
                  AND patient.role = 'patient'
                """,
                (interaction_request_id, session_id),
            ).fetchone()
            if (
                interaction is None
                or interaction["processing_status"] != "completed"
                or interaction["patient_message_id"] is None
                or interaction["session_id"] != session_id
            ):
                raise MemoryRequestNotCompletedError(
                    "Memory extraction requires its completed interaction."
                )
            rows = connection.execute(
                """
                SELECT message_id, role, content
                FROM messages
                WHERE session_id = ?
                  AND message_id IN (?, ?)
                ORDER BY sequence_number
                """,
                (
                    session_id,
                    interaction["therapist_message_id"],
                    interaction["patient_message_id"],
                ),
            ).fetchall()
            return [
                {
                    "message_id": row["message_id"],
                    "role": row["role"],
                    "content": row["content"],
                }
                for row in rows
            ]

    def _complete(
        self,
        job: sqlite3.Row,
        *,
        candidate_count: int,
        output_hash: str,
        model_identifier: str,
        model_run_id: str | None,
    ) -> None:
        completed_at = self._format_utc(self._now())
        with self._database_manager.transaction("operational") as connection:
            repository = MemoryExtractionJobRepository(connection)
            if not repository.mark_completed(
                job["job_id"],
                worker_id=self._worker_id,
                candidate_count=candidate_count,
                completed_at=completed_at,
            ):
                raise RuntimeError("Memory extraction job lease was lost.")
            AuditRepository(connection).record(
                audit_event_id=f"memory-extraction-audit-{uuid.uuid4().hex}",
                component="memory_extraction_worker",
                operation_type="memory_extraction_completed",
                entity_type="memory_extraction_job",
                entity_id=job["job_id"],
                run_id=job["run_id"],
                session_id=job["session_id"],
                operation_status="succeeded",
                metadata={
                    "attempt_count": job["attempt_count"],
                    "candidate_count": candidate_count,
                    "interaction_request_id": job["interaction_request_id"],
                    "model_identifier": model_identifier,
                    "model_run_id": model_run_id,
                    "provider": self._agent.client.config.name,
                    "output_hash": output_hash,
                    "prompt_id": MEMORY_EXTRACTION_PROMPT_ID,
                    "prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                    "schema_version": MEMORY_EXTRACTION_SCHEMA_VERSION,
                    "temperature": 0.0,
                    "max_tokens": self._agent.max_tokens,
                },
                created_at=completed_at,
            )

    def _retry_time(self, attempt_count: int) -> str:
        delay_seconds = min(300, 2 ** max(0, attempt_count - 1))
        return self._format_utc(
            self._now() + timedelta(seconds=delay_seconds)
        )

    def _fail(
        self,
        job: sqlite3.Row,
        *,
        error_code: str,
        retryable: bool,
        model_run_id: str | None,
    ) -> None:
        failed_at = self._format_utc(self._now())
        with self._database_manager.transaction("operational") as connection:
            repository = MemoryExtractionJobRepository(connection)
            changed = repository.mark_failed(
                job["job_id"],
                worker_id=self._worker_id,
                error_code=error_code,
                retry_at=self._retry_time(job["attempt_count"]),
                failed_at=failed_at,
                max_attempts=MAX_ATTEMPTS,
                retryable=retryable,
            )
            if not changed:
                raise RuntimeError("Memory extraction job lease was lost.")
            AuditRepository(connection).record(
                audit_event_id=f"memory-extraction-audit-{uuid.uuid4().hex}",
                component="memory_extraction_worker",
                operation_type="memory_extraction_attempt_failed",
                entity_type="memory_extraction_job",
                entity_id=job["job_id"],
                run_id=job["run_id"],
                session_id=job["session_id"],
                operation_status="failed",
                metadata={
                    "attempt_count": job["attempt_count"],
                    "error_code": error_code,
                    "interaction_request_id": job["interaction_request_id"],
                    "model_identifier": self._agent.model,
                    "model_run_id": model_run_id,
                    "provider": self._agent.client.config.name,
                    "prompt_id": MEMORY_EXTRACTION_PROMPT_ID,
                    "prompt_version": MEMORY_EXTRACTION_PROMPT_VERSION,
                },
                created_at=failed_at,
            )

    @staticmethod
    def _error_code(error: Exception) -> str:
        if isinstance(error, ProviderConnectionError):
            return "provider_unavailable"
        if isinstance(error, ProviderResponseError):
            return "provider_error"
        if isinstance(error, MemoryExtractionAgentError):
            return "invalid_memory_extraction_output"
        if isinstance(error, MemoryRequestNotFoundError):
            return "source_interaction_not_found"
        if isinstance(error, MemoryRequestNotCompletedError):
            return "source_interaction_not_completed"
        if isinstance(error, MemoryEvidenceValidationError):
            return "invalid_memory_evidence"
        if isinstance(error, MemoryReviewConflictError):
            return "memory_revision_conflict"
        if isinstance(error, MemoryIdempotencyConflictError):
            return "memory_idempotency_conflict"
        if isinstance(error, TimeoutError):
            return "provider_timeout"
        return "memory_extraction_internal_error"

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        return not isinstance(
            error,
            (
                MemoryRequestNotFoundError,
                MemoryRequestNotCompletedError,
                MemoryEvidenceValidationError,
                MemoryIdempotencyConflictError,
                MemoryReviewConflictError,
            ),
        )

    def process_one(self) -> bool:
        """Claim and process one job; return False when no work is ready."""

        job = self._claim()
        if job is None:
            return False
        model_run_id = job["model_run_id"]
        model_run_active = False
        try:
            if job["proposal_payload"] is not None:
                try:
                    output = MemoryExtractionOutput.model_validate_json(
                        job["proposal_payload"]
                    )
                except ValidationError:
                    raise MemoryExtractionAgentError(
                        "Saved memory proposals failed schema validation."
                    ) from None
                output_hash = job["output_hash"]
            else:
                messages = self._load_transcript(
                    interaction_request_id=job["interaction_request_id"],
                    session_id=job["session_id"],
                )
                input_messages = self._agent.prepare_messages(
                    interaction_request_id=job["interaction_request_id"],
                    messages=messages,
                )
                model_run_id = self._start_model_run(
                    job,
                    input_messages=input_messages,
                )
                model_run_active = True
                output = self._agent._extract_prepared_messages(input_messages)
                proposal_payload = output.model_dump_json()
                output_hash = self._digest_text(proposal_payload)
                output_saved_at = self._format_utc(self._now())
                with self._database_manager.transaction(
                    "operational"
                ) as connection:
                    saved = MemoryExtractionJobRepository(
                        connection
                    ).save_proposals(
                        job["job_id"],
                        worker_id=self._worker_id,
                        proposal_payload=proposal_payload,
                        output_hash=output_hash,
                        updated_at=output_saved_at,
                    )
                    if not saved:
                        raise RuntimeError(
                            "Memory extraction job lease was lost before "
                            "saving proposals."
                        )
                    if not ModelRunRepository(connection).complete(
                        model_run_id,
                        completed_at=output_saved_at,
                        output_hash=output_hash,
                        output_validation_status="valid",
                    ):
                        raise RuntimeError(
                            "Memory extraction model run was no longer active."
                        )
                model_run_active = False
            created_at = self._format_utc(self._now())
            for proposal_index, item in enumerate(output.proposals):
                self._memory_service.create_candidate(
                    run_id=job["run_id"],
                    session_id=job["session_id"],
                    interaction_request_id=job["interaction_request_id"],
                    proposal_index=proposal_index,
                    memory_scope=item.memory_scope,
                    proposal=item.proposal,
                    created_at=created_at,
                    require_patient_authored_evidence=True,
                )
            self._complete(
                job,
                candidate_count=len(output.proposals),
                output_hash=output_hash,
                model_identifier=self._agent.model,
                model_run_id=model_run_id,
            )
        except Exception as exc:
            error_code = self._error_code(exc)
            LOGGER.exception(
                "Memory extraction job failed (job_id=%s, error_code=%s)",
                job["job_id"],
                error_code,
            )
            if model_run_id is not None and model_run_active:
                with self._database_manager.transaction(
                    "operational"
                ) as connection:
                    ModelRunRepository(connection).fail(
                        model_run_id,
                        completed_at=self._format_utc(self._now()),
                        output_validation_status=(
                            "invalid"
                            if isinstance(exc, MemoryExtractionAgentError)
                            else "not_validated"
                        ),
                    )
            self._fail(
                job,
                error_code=error_code,
                retryable=self._is_retryable(exc),
                model_run_id=model_run_id,
            )
        return True

    async def run_forever(self) -> None:
        """Run until requested to stop, finishing any currently leased job."""

        while not self._stop_requested.is_set():
            try:
                worked = await asyncio.to_thread(self.process_one)
            except Exception:
                LOGGER.exception("Memory extraction worker iteration failed.")
                worked = False
            if not worked and not self._stop_requested.is_set():
                await asyncio.sleep(self._poll_interval_seconds)

    def request_stop(self) -> None:
        """Stop after the current leased job reaches a durable state."""

        self._stop_requested.set()
