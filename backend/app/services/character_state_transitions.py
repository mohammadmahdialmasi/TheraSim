"""Evidence validation and explicit review for character-state transitions."""

from __future__ import annotations

import sqlite3
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.character_runtime import (
    CHARACTER_STATE_BOUNDS,
    RunCharacterRepository,
)
from app.services.character_model import CharacterStateTransitionProposal


class CharacterStateTransitionError(RuntimeError):
    """Base error for character-state transition operations."""


class CharacterStateTransitionNotFoundError(CharacterStateTransitionError):
    """The requested transition does not exist."""


class CharacterStateTransitionEvidenceError(CharacterStateTransitionError):
    """Evidence does not belong to the requested run and session."""


class CharacterStateTransitionConflictError(CharacterStateTransitionError):
    """The proposal conflicts with an existing or newer state."""


class CharacterStateTransitionIntegrityError(CharacterStateTransitionError):
    """Persisted character-state data is inconsistent."""


class CharacterStateTransitionService:
    """Records untrusted proposals and applies only explicitly reviewed changes.

    A submitted proposal is never applied automatically. Acceptance creates
    a new immutable state snapshot in the same transaction that records the
    review decision.
    """

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        self._database_manager = database_manager

    @staticmethod
    def _require_text(value: object, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")
        return value

    @staticmethod
    def _load_evidence(
        connection: sqlite3.Connection,
        *,
        run_id: str,
        session_id: str,
        message_ids: tuple[str, ...],
    ) -> list[sqlite3.Row]:
        if not message_ids or len(message_ids) != len(set(message_ids)):
            raise CharacterStateTransitionEvidenceError(
                "Transition evidence must contain unique persisted message IDs."
            )

        placeholders = ",".join("?" for _ in message_ids)
        rows = connection.execute(
            f"""
            SELECT
                message.message_id,
                message.role,
                session.run_id,
                session.session_id
            FROM messages AS message
            JOIN sessions AS session
              ON session.session_id = message.session_id
            WHERE message.message_id IN ({placeholders})
            """,
            message_ids,
        ).fetchall()

        if len(rows) != len(message_ids):
            raise CharacterStateTransitionEvidenceError(
                "One or more evidence messages do not exist."
            )

        for row in rows:
            if (
                row["run_id"] != run_id
                or row["session_id"] != session_id
            ):
                raise CharacterStateTransitionEvidenceError(
                    "Evidence must belong to the same run and session."
                )

        if not any(row["role"] == "patient" for row in rows):
            raise CharacterStateTransitionEvidenceError(
                "At least one patient-authored evidence message is required."
            )

        return rows

    @staticmethod
    def _validate_current_state(
        repository: RunCharacterRepository,
        run_id: str,
    ) -> tuple[sqlite3.Row, dict[str, int]]:
        try:
            head = repository.get_current_state_snapshot(run_id)
        except ValueError as exc:
            raise CharacterStateTransitionIntegrityError(
                "Character-state history has multiple current heads."
            ) from exc

        if head is None:
            raise CharacterStateTransitionIntegrityError(
                "The run has no current character-state snapshot."
            )

        values = repository.get_state_snapshot_values(head["snapshot_id"])

        if set(values) != set(CHARACTER_STATE_BOUNDS):
            raise CharacterStateTransitionIntegrityError(
                "The current character-state snapshot is incomplete."
            )

        return head, values

    @staticmethod
    def _matches_existing_proposal(
        repository: RunCharacterRepository,
        existing: sqlite3.Row,
        proposal: CharacterStateTransitionProposal,
    ) -> bool:
        same_fields = (
            existing["run_id"] == proposal.run_id
            and existing["session_id"] == proposal.session_id
            and existing["variable_name"] == proposal.variable_name
            and existing["previous_value"] == proposal.previous_value
            and existing["proposed_value"] == proposal.proposed_value
            and existing["uncertainty_notes"] == proposal.rationale
            and existing["confidence"] == proposal.confidence
        )

        existing_evidence = {
            row["message_id"]
            for row in repository.get_state_transition_evidence(
                existing["transition_id"]
            )
        }

        return same_fields and existing_evidence == set(
            proposal.evidence_message_ids
        )

    def submit_proposal(
        self,
        proposal: CharacterStateTransitionProposal,
        *,
        created_at: str,
    ) -> dict[str, object]:
        """Persist a proposal for review without changing character state."""

        if not isinstance(proposal, CharacterStateTransitionProposal):
            raise TypeError("A CharacterStateTransitionProposal is required.")

        self._require_text(created_at, "created_at")

        with self._database_manager.transaction("operational") as connection:
            evidence = self._load_evidence(
                connection,
                run_id=proposal.run_id,
                session_id=proposal.session_id,
                message_ids=proposal.evidence_message_ids,
            )

            repository = RunCharacterRepository(connection)
            existing = repository.get_state_transition_by_idempotency_key(
                proposal.run_id,
                proposal.proposal_id,
            )

            if existing is not None:
                if self._matches_existing_proposal(
                    repository,
                    existing,
                    proposal,
                ):
                    return dict(existing)

                raise CharacterStateTransitionConflictError(
                    "The idempotency key was already used for a different proposal."
                )

            _, current_values = self._validate_current_state(
                repository,
                proposal.run_id,
            )

            current_value = current_values[proposal.variable_name]

            if current_value != proposal.previous_value:
                raise CharacterStateTransitionConflictError(
                    "The proposal was based on an outdated character state."
                )

            transition_id = f"transition-{uuid.uuid4().hex}"

            repository.create_state_transition(
                transition_id=transition_id,
                run_id=proposal.run_id,
                session_id=proposal.session_id,
                variable_name=proposal.variable_name,
                previous_value=proposal.previous_value,
                proposed_value=proposal.proposed_value,
                validation_status="requires_review",
                idempotency_key=proposal.proposal_id,
                created_at=created_at,
                confidence=proposal.confidence,
                uncertainty_notes=proposal.rationale,
            )

            for item in evidence:
                repository.add_state_transition_evidence(
                    transition_id,
                    item["message_id"],
                    "supports",
                    proposal.rationale,
                )

            stored = repository.get_state_transition(transition_id)
            if stored is None:
                raise CharacterStateTransitionIntegrityError(
                    "Created transition could not be read."
                )

            return dict(stored)

    def accept_transition(
        self,
        transition_id: str,
        *,
        validated_at: str,
        accepted_value: int | None = None,
    ) -> dict[str, object]:
        """Accept a reviewed proposal and atomically append a new snapshot."""

        self._require_text(transition_id, "transition_id")
        self._require_text(validated_at, "validated_at")

        with self._database_manager.transaction("operational") as connection:
            repository = RunCharacterRepository(connection)
            transition = repository.get_state_transition(transition_id)

            if transition is None:
                raise CharacterStateTransitionNotFoundError(
                    "Transition does not exist."
                )

            if transition["validation_status"] == "accepted":
                expected = (
                    transition["proposed_value"]
                    if accepted_value is None
                    else accepted_value
                )
                if expected != transition["accepted_value"]:
                    raise CharacterStateTransitionConflictError(
                        "Transition was already accepted with a different value."
                    )
                return dict(transition)

            if transition["validation_status"] == "rejected":
                raise CharacterStateTransitionConflictError(
                    "A rejected transition cannot be accepted."
                )

            evidence_ids = tuple(
                row["message_id"]
                for row in repository.get_state_transition_evidence(
                    transition_id
                )
            )

            self._load_evidence(
                connection,
                run_id=transition["run_id"],
                session_id=transition["session_id"],
                message_ids=evidence_ids,
            )

            head, current_values = self._validate_current_state(
                repository,
                transition["run_id"],
            )

            variable_name = transition["variable_name"]
            current_value = current_values[variable_name]

            # A proposal based on a no-longer-current value is rejected.
            # This decision is persisted, but no new state snapshot is created.
            if current_value != transition["previous_value"]:
                if not repository.resolve_state_transition(
                    transition_id,
                    validation_status="rejected",
                    validated_at=validated_at,
                ):
                    raise CharacterStateTransitionConflictError(
                        "Transition changed during review."
                    )

                rejected = repository.get_state_transition(transition_id)
                return dict(rejected)

            chosen_value = (
                transition["proposed_value"]
                if accepted_value is None
                else accepted_value
            )

            bounds = CHARACTER_STATE_BOUNDS[variable_name]
            if (
                isinstance(chosen_value, bool)
                or not isinstance(chosen_value, int)
                or not bounds[0] <= chosen_value <= bounds[1]
            ):
                raise ValueError("Accepted value is outside the allowed bounds.")

            if chosen_value != current_value:
                next_values = dict(current_values)
                next_values[variable_name] = chosen_value

                repository.create_state_snapshot(
                    snapshot_id=f"character-state-{uuid.uuid4().hex}",
                    run_id=transition["run_id"],
                    session_id=transition["session_id"],
                    previous_snapshot_id=head["snapshot_id"],
                    state_schema_version=head["state_schema_version"],
                    snapshot_reason="reviewed_transition",
                    created_at=validated_at,
                    values=next_values,
                )

            if not repository.resolve_state_transition(
                transition_id,
                validation_status="accepted",
                validated_at=validated_at,
                accepted_value=chosen_value,
            ):
                raise CharacterStateTransitionConflictError(
                    "Transition changed during review."
                )

            accepted = repository.get_state_transition(transition_id)
            return dict(accepted)

    def reject_transition(
        self,
        transition_id: str,
        *,
        validated_at: str,
    ) -> dict[str, object]:
        """Reject a proposal without changing the current character state."""

        self._require_text(transition_id, "transition_id")
        self._require_text(validated_at, "validated_at")

        with self._database_manager.transaction("operational") as connection:
            repository = RunCharacterRepository(connection)
            transition = repository.get_state_transition(transition_id)

            if transition is None:
                raise CharacterStateTransitionNotFoundError(
                    "Transition does not exist."
                )

            if transition["validation_status"] == "rejected":
                return dict(transition)

            if transition["validation_status"] == "accepted":
                raise CharacterStateTransitionConflictError(
                    "An accepted transition cannot be rejected."
                )

            if not repository.resolve_state_transition(
                transition_id,
                validation_status="rejected",
                validated_at=validated_at,
            ):
                raise CharacterStateTransitionConflictError(
                    "Transition changed during review."
                )

            rejected = repository.get_state_transition(transition_id)
            return dict(rejected)
