"""Repository for immutable state snapshots and validated transitions."""

import sqlite3
from collections.abc import Mapping

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    require_message_for_run,
    require_session_for_run,
    require_text,
)


STATE_VARIABLES = {
    "therapeutic_alliance",
    "disclosure_readiness",
    "experiential_avoidance",
    "willingness",
    "values_clarity",
    "committed_action_readiness",
}
TRANSITION_STATUSES = {"pending", "accepted", "rejected", "requires_review"}


class StateRepository(ConnectionBoundRepository):
    """Persists state records; does not infer or approve psychological change."""

    def get_snapshot(self, snapshot_id: str) -> sqlite3.Row | None:
        self.require_text(snapshot_id, "snapshot_id")
        return self._connection.execute(
            "SELECT * FROM state_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

    def get_snapshot_values(self, snapshot_id: str) -> dict[str, int]:
        self.require_text(snapshot_id, "snapshot_id")
        rows = self._connection.execute(
            """
            SELECT variable_name, variable_value
            FROM state_snapshot_values
            WHERE snapshot_id = ?
            ORDER BY variable_name
            """,
            (snapshot_id,),
        ).fetchall()
        return {row["variable_name"]: row["variable_value"] for row in rows}

    def create_snapshot(
        self,
        *,
        snapshot_id: str,
        run_id: str,
        state_schema_version: str,
        snapshot_reason: str,
        created_at: str,
        values: Mapping[str, int],
        session_id: str | None = None,
        previous_snapshot_id: str | None = None,
    ) -> None:
        for name, value in (
            ("snapshot_id", snapshot_id),
            ("run_id", run_id),
            ("state_schema_version", state_schema_version),
            ("snapshot_reason", snapshot_reason),
            ("created_at", created_at),
        ):
            require_text(value, name)

        if not isinstance(values, Mapping) or not values:
            raise ValueError("Snapshot values must be a non-empty mapping.")

        unknown = set(values) - STATE_VARIABLES
        if unknown:
            raise ValueError(f"Unknown state variables: {sorted(unknown)}")

        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
                raise ValueError(f"Invalid value for state variable {name}.")

        if session_id is not None:
            require_session_for_run(self._connection, session_id, run_id)

        if previous_snapshot_id is not None:
            previous = self.get_snapshot(previous_snapshot_id)
            if previous is None or previous["run_id"] != run_id:
                raise ValueError("Previous snapshot belongs to another run or is missing.")

        self._connection.execute(
            """
            INSERT INTO state_snapshots (
                snapshot_id, run_id, session_id,
                previous_snapshot_id, state_schema_version,
                snapshot_reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                session_id,
                previous_snapshot_id,
                state_schema_version,
                snapshot_reason,
                created_at,
            ),
        )

        for name, value in values.items():
            self._connection.execute(
                """
                INSERT INTO state_snapshot_values
                (snapshot_id, variable_name, variable_value)
                VALUES (?, ?, ?)
                """,
                (snapshot_id, name, value),
            )

    def create_transition(
        self,
        *,
        transition_id: str,
        run_id: str,
        session_id: str,
        variable_name: str,
        previous_value: int,
        proposed_value: int,
        validation_status: str,
        idempotency_key: str,
        created_at: str,
        event_id: str | None = None,
        accepted_value: int | None = None,
        transition_rule_id: str | None = None,
        transition_rule_version: str | None = None,
        resulting_snapshot_id: str | None = None,
        confidence: str | None = None,
        uncertainty_notes: str | None = None,
        validated_at: str | None = None,
    ) -> None:
        for name, value in (
            ("transition_id", transition_id),
            ("run_id", run_id),
            ("session_id", session_id),
            ("variable_name", variable_name),
            ("idempotency_key", idempotency_key),
            ("created_at", created_at),
        ):
            require_text(value, name)

        if variable_name not in STATE_VARIABLES:
            raise ValueError("Unknown state variable.")

        if validation_status not in TRANSITION_STATUSES:
            raise ValueError("Invalid transition status.")

        for name, value in (
            ("previous_value", previous_value),
            ("proposed_value", proposed_value),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
                raise ValueError(f"{name} must be an integer between 0 and 4.")

        if validation_status == "accepted":
            if isinstance(accepted_value, bool) or not isinstance(accepted_value, int) or not 0 <= accepted_value <= 4:
                raise ValueError("Accepted transitions require an accepted value.")
        elif accepted_value is not None:
            raise ValueError("Non-accepted transitions cannot have an accepted value.")

        require_session_for_run(self._connection, session_id, run_id)

        if event_id is not None:
            event = self._connection.execute(
                "SELECT run_id FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if event is None or event["run_id"] != run_id:
                raise ValueError("Transition event belongs to another run.")

        if resulting_snapshot_id is not None:
            snapshot = self.get_snapshot(resulting_snapshot_id)
            if snapshot is None or snapshot["run_id"] != run_id:
                raise ValueError("Resulting snapshot belongs to another run.")

            if validation_status != "accepted":
                raise ValueError("Only accepted transitions may link a resulting snapshot.")

        self._connection.execute(
            """
            INSERT INTO state_transitions (
                transition_id, run_id, session_id, event_id,
                variable_name, previous_value, proposed_value,
                accepted_value, validation_status,
                transition_rule_id, transition_rule_version,
                resulting_snapshot_id, confidence, uncertainty_notes,
                idempotency_key, created_at, validated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transition_id,
                run_id,
                session_id,
                event_id,
                variable_name,
                previous_value,
                proposed_value,
                accepted_value,
                validation_status,
                transition_rule_id,
                transition_rule_version,
                resulting_snapshot_id,
                confidence,
                uncertainty_notes,
                idempotency_key,
                created_at,
                validated_at,
            ),
        )

    def resolve_transition(
        self,
        transition_id: str,
        *,
        validation_status: str,
        validated_at: str,
        accepted_value: int | None = None,
        resulting_snapshot_id: str | None = None,
        uncertainty_notes: str | None = None,
    ) -> bool:
        require_text(transition_id, "transition_id")
        require_text(validated_at, "validated_at")

        if validation_status not in TRANSITION_STATUSES - {"pending"}:
            raise ValueError("Resolution status must be accepted, rejected, or requires_review.")

        if validation_status == "accepted":
            if isinstance(accepted_value, bool) or not isinstance(accepted_value, int) or not 0 <= accepted_value <= 4:
                raise ValueError("Accepted transition requires a value.")
            if resulting_snapshot_id is None:
                raise ValueError("Accepted transition requires a resulting snapshot.")
        elif accepted_value is not None or resulting_snapshot_id is not None:
            raise ValueError("Rejected or review-required transitions cannot change state.")

        row = self._connection.execute(
            "SELECT * FROM state_transitions WHERE transition_id = ?",
            (transition_id,),
        ).fetchone()

        if row is None:
            raise ValueError("Transition does not exist.")

        if row["validation_status"] != "pending":
            if (
                row["validation_status"] == validation_status
                and row["accepted_value"] == accepted_value
                and row["resulting_snapshot_id"] == resulting_snapshot_id
            ):
                return False
            raise ValueError("Only pending transitions can be resolved.")

        if resulting_snapshot_id is not None:
            snapshot = self.get_snapshot(resulting_snapshot_id)
            if snapshot is None or snapshot["run_id"] != row["run_id"]:
                raise ValueError("Resulting snapshot belongs to another run.")

        self._connection.execute(
            """
            UPDATE state_transitions
            SET validation_status = ?,
                accepted_value = ?,
                resulting_snapshot_id = ?,
                uncertainty_notes = ?,
                validated_at = ?
            WHERE transition_id = ?
            """,
            (
                validation_status,
                accepted_value,
                resulting_snapshot_id,
                uncertainty_notes,
                validated_at,
                transition_id,
            ),
        )
        return True

    def add_transition_evidence(
        self,
        transition_id: str,
        message_id: str,
        *,
        evidence_role: str,
        relevance_note: str | None = None,
    ) -> bool:
        require_text(transition_id, "transition_id")
        require_text(message_id, "message_id")
        require_text(evidence_role, "evidence_role")

        transition = self._connection.execute(
            "SELECT run_id FROM state_transitions WHERE transition_id = ?",
            (transition_id,),
        ).fetchone()

        if transition is None:
            raise ValueError("Transition does not exist.")

        require_message_for_run(
            self._connection,
            message_id,
            transition["run_id"],
        )

        existing = self._connection.execute(
            """
            SELECT * FROM transition_evidence
            WHERE transition_id = ? AND message_id = ?
            """,
            (transition_id, message_id),
        ).fetchone()

        if existing is not None:
            if (
                existing["evidence_role"] == evidence_role
                and existing["relevance_note"] == relevance_note
            ):
                return False
            raise ValueError("Transition evidence already exists with different data.")

        self._connection.execute(
            """
            INSERT INTO transition_evidence
            (transition_id, message_id, evidence_role, relevance_note)
            VALUES (?, ?, ?, ?)
            """,
            (transition_id, message_id, evidence_role, relevance_note),
        )
        return True

    def list_transitions(self, run_id: str) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM state_transitions
                WHERE run_id = ?
                ORDER BY created_at, transition_id
                """,
                (run_id,),
            ).fetchall()
        )
