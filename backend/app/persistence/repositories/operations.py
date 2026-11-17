"""Repositories for model execution metadata and audit events."""

import sqlite3
from collections.abc import Mapping

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    json_text,
    require_session_for_run,
    require_text,
)


MODEL_COMPONENTS = {
    "patient_agent",
    "evaluator_agent",
    "memory_extraction_agent",
}


class ModelRunRepository(ConnectionBoundRepository):
    def create_model_run(
        self,
        *,
        model_run_id: str,
        component: str,
        provider: str,
        model_identifier: str,
        execution_status: str,
        started_at: str,
        generation_parameters: Mapping[str, object],
        run_id: str | None = None,
        session_id: str | None = None,
        model_version: str | None = None,
        model_artifact_digest: str | None = None,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
        input_schema_version: str | None = None,
        output_schema_version: str | None = None,
        input_hash: str | None = None,
        random_seed: int | None = None,
    ) -> None:
        for name, value in (
            ("model_run_id", model_run_id),
            ("component", component),
            ("provider", provider),
            ("model_identifier", model_identifier),
            ("execution_status", execution_status),
            ("started_at", started_at),
        ):
            require_text(value, name)

        if component not in MODEL_COMPONENTS:
            raise ValueError("Invalid model component.")

        if execution_status not in {"in_progress", "completed", "failed"}:
            raise ValueError("Invalid model execution status.")

        if session_id is not None:
            if run_id is None:
                raise ValueError("Session-scoped model run requires run_id.")
            require_session_for_run(self._connection, session_id, run_id)

        if random_seed is not None and (
            isinstance(random_seed, bool) or not isinstance(random_seed, int)
        ):
            raise ValueError("Random seed must be an integer or None.")

        self._connection.execute(
            """
            INSERT INTO model_runs (
                model_run_id, run_id, session_id, component, provider,
                model_identifier, model_version, model_artifact_digest,
                prompt_id, prompt_version, input_schema_version,
                output_schema_version, generation_parameters,
                input_hash, output_hash, random_seed, execution_status,
                output_validation_status, started_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, NULL)
            """,
            (
                model_run_id,
                run_id,
                session_id,
                component,
                provider,
                model_identifier,
                model_version,
                model_artifact_digest,
                prompt_id,
                prompt_version,
                input_schema_version,
                output_schema_version,
                json_text(generation_parameters, "generation_parameters"),
                input_hash,
                random_seed,
                execution_status,
                started_at,
            ),
        )

    def get(self, model_run_id: str) -> sqlite3.Row | None:
        self.require_text(model_run_id, "model_run_id")
        return self._connection.execute(
            "SELECT * FROM model_runs WHERE model_run_id = ?",
            (model_run_id,),
        ).fetchone()

    def set_input_hash(
        self,
        model_run_id: str,
        input_hash: str,
    ) -> bool:
        """Set an immutable input hash while the model run is in progress."""

        require_text(model_run_id, "model_run_id")
        require_text(input_hash, "input_hash")

        model = self.get(model_run_id)
        if model is None or model["execution_status"] != "in_progress":
            return False

        current_hash = model["input_hash"]

        if current_hash is not None:
            return current_hash == input_hash

        cursor = self._connection.execute(
            """
            UPDATE model_runs
            SET input_hash = ?
            WHERE model_run_id = ?
              AND execution_status = 'in_progress'
              AND input_hash IS NULL
            """,
            (input_hash, model_run_id),
        )
        return cursor.rowcount == 1

    def complete(
        self,
        model_run_id: str,
        *,
        completed_at: str,
        output_hash: str | None,
        output_validation_status: str,
    ) -> bool:
        for name, value in (
            ("model_run_id", model_run_id),
            ("completed_at", completed_at),
            ("output_validation_status", output_validation_status),
        ):
            require_text(value, name)

        cursor = self._connection.execute(
            """
            UPDATE model_runs
            SET execution_status = 'completed',
                completed_at = ?,
                output_hash = ?,
                output_validation_status = ?
            WHERE model_run_id = ? AND execution_status = 'in_progress'
            """,
            (
                completed_at,
                output_hash,
                output_validation_status,
                model_run_id,
            ),
        )
        return cursor.rowcount == 1

    def fail(
        self,
        model_run_id: str,
        *,
        completed_at: str,
        output_validation_status: str = "not_validated",
    ) -> bool:
        for name, value in (
            ("model_run_id", model_run_id),
            ("completed_at", completed_at),
            ("output_validation_status", output_validation_status),
        ):
            require_text(value, name)

        cursor = self._connection.execute(
            """
            UPDATE model_runs
            SET execution_status = 'failed',
                completed_at = ?,
                output_validation_status = ?
            WHERE model_run_id = ? AND execution_status = 'in_progress'
            """,
            (
                completed_at,
                output_validation_status,
                model_run_id,
            ),
        )
        return cursor.rowcount == 1


class AuditRepository(ConnectionBoundRepository):
    """Append-only persistence for operational audit records."""

    def record(
        self,
        *,
        audit_event_id: str,
        component: str,
        operation_type: str,
        entity_type: str,
        operation_status: str,
        created_at: str,
        entity_id: str | None = None,
        run_id: str | None = None,
        session_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        for name, value in (
            ("audit_event_id", audit_event_id),
            ("component", component),
            ("operation_type", operation_type),
            ("entity_type", entity_type),
            ("operation_status", operation_status),
            ("created_at", created_at),
        ):
            require_text(value, name)

        if session_id is not None:
            if run_id is None:
                raise ValueError("Session audit event requires run_id.")
            require_session_for_run(self._connection, session_id, run_id)

        serialized_metadata = (
            json_text(metadata, "metadata")
            if metadata is not None
            else None
        )

        self._connection.execute(
            """
            INSERT INTO audit_events (
                audit_event_id, component, operation_type,
                entity_type, entity_id, run_id, session_id,
                operation_status, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_event_id,
                component,
                operation_type,
                entity_type,
                entity_id,
                run_id,
                session_id,
                operation_status,
                serialized_metadata,
                created_at,
            ),
        )

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[sqlite3.Row]:
        require_text(entity_type, "entity_type")
        require_text(entity_id, "entity_id")

        return list(
            self._connection.execute(
                """
                SELECT * FROM audit_events
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY created_at, audit_event_id
                """,
                (entity_type, entity_id),
            ).fetchall()
        )
