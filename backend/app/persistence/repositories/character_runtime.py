"""Operational repositories for run-specific character snapshots."""

import sqlite3
from collections.abc import Mapping

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import require_session_for_run, require_text


CHARACTER_STATE_BOUNDS = {
    "affect_valence": (-2, 2),
    "arousal": (0, 4),
    "perceived_safety": (0, 4),
    "social_evaluative_threat": (0, 4),
    "engagement": (0, 4),
    "interpersonal_withdrawal": (0, 4),
}

DEFAULT_CHARACTER_STATE_VALUES = {
    "affect_valence": 0,
    "arousal": 2,
    "perceived_safety": 2,
    "social_evaluative_threat": 2,
    "engagement": 2,
    "interpersonal_withdrawal": 2,
}


class RunCharacterRepository(ConnectionBoundRepository):
    """Persists run-local profile references and immutable dynamic-state snapshots.

    The full personality profile remains in the restricted Case Vault. The
    operational database stores only its immutable version/hash reference.
    """

    def create_profile_snapshot(
        self,
        *,
        snapshot_id: str,
        run_id: str,
        case_id: str,
        case_version_id: str,
        character_id: str,
        profile_status: str,
        personality_profile_id: str | None,
        profile_version: int | None,
        personality_schema_version: str,
        theory_bundle_version: str | None,
        source_content_hash: str | None,
        captured_at: str,
    ) -> None:
        for name, value in (
            ("snapshot_id", snapshot_id),
            ("run_id", run_id),
            ("case_id", case_id),
            ("case_version_id", case_version_id),
            ("character_id", character_id),
            ("personality_schema_version", personality_schema_version),
            ("captured_at", captured_at),
        ):
            require_text(value, name)

        if profile_status not in {"unconfigured", "active"}:
            raise ValueError("Invalid character profile snapshot status.")

        if profile_status == "unconfigured":
            if any(value is not None for value in (
                personality_profile_id, profile_version,
                theory_bundle_version, source_content_hash,
            )):
                raise ValueError("Unconfigured profile snapshots cannot reference a profile.")
            if character_id != "UNCONFIGURED_CHARACTER":
                raise ValueError("Unconfigured snapshots require the explicit sentinel ID.")
        else:
            require_text(personality_profile_id, "personality_profile_id")
            require_text(theory_bundle_version, "theory_bundle_version")
            require_text(source_content_hash, "source_content_hash")
            if (
                isinstance(profile_version, bool)
                or not isinstance(profile_version, int)
                or profile_version < 1
            ):
                raise ValueError("Profile version must be a positive integer.")
            if (
                len(source_content_hash) != 64
                or any(c not in "0123456789abcdef" for c in source_content_hash)
            ):
                raise ValueError("Source content hash must be lowercase SHA-256.")

        self._connection.execute(
            """
            INSERT INTO run_character_profiles (
                snapshot_id,
                run_id,
                case_id,
                case_version_id,
                character_id,
                personality_profile_id,
                profile_version,
                personality_schema_version,
                theory_bundle_version,
                source_content_hash,
                profile_status,
                captured_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                run_id,
                case_id,
                case_version_id,
                character_id,
                personality_profile_id,
                profile_version,
                personality_schema_version,
                theory_bundle_version,
                source_content_hash,
                profile_status,
                captured_at,
            ),
        )

    def get_profile_snapshot(self, run_id: str) -> sqlite3.Row | None:
        require_text(run_id, "run_id")
        return self._connection.execute(
            "SELECT * FROM run_character_profiles WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    def create_state_snapshot(
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

        if not isinstance(values, Mapping):
            raise ValueError("Character state values must be a mapping.")
        if set(values) != set(CHARACTER_STATE_BOUNDS):
            raise ValueError(
                "Character state snapshot must contain exactly all six variables."
            )

        for name, value in values.items():
            minimum, maximum = CHARACTER_STATE_BOUNDS[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise ValueError(f"Invalid value for character state variable {name}.")

        if session_id is not None:
            require_session_for_run(self._connection, session_id, run_id)

        if previous_snapshot_id is None:
            existing_root = self._connection.execute(
                """
                SELECT snapshot_id FROM character_state_snapshots
                WHERE run_id = ? AND previous_snapshot_id IS NULL
                """,
                (run_id,),
            ).fetchone()
            if existing_root is not None:
                raise ValueError("Run already has an initial character state snapshot.")
        else:
            previous = self._connection.execute(
                """
                SELECT snapshot_id FROM character_state_snapshots
                WHERE snapshot_id = ? AND run_id = ?
                """,
                (previous_snapshot_id, run_id),
            ).fetchone()
            if previous is None:
                raise ValueError(
                    "Previous character snapshot is missing or belongs to another run."
                )
            child = self._connection.execute(
                """
                SELECT snapshot_id FROM character_state_snapshots
                WHERE previous_snapshot_id = ?
                """,
                (previous_snapshot_id,),
            ).fetchone()
            if child is not None:
                raise ValueError("Previous snapshot is not the current chain head.")

        self._connection.execute(
            """
            INSERT INTO character_state_snapshots (
                snapshot_id, run_id, session_id, previous_snapshot_id,
                state_schema_version, snapshot_reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id, run_id, session_id, previous_snapshot_id,
                state_schema_version, snapshot_reason, created_at,
            ),
        )

        for name in sorted(values):
            self._connection.execute(
                """
                INSERT INTO character_state_snapshot_values (
                    snapshot_id, variable_name, variable_value
                ) VALUES (?, ?, ?)
                """,
                (snapshot_id, name, values[name]),
            )

    def get_state_snapshot(self, snapshot_id: str) -> sqlite3.Row | None:
        require_text(snapshot_id, "snapshot_id")
        return self._connection.execute(
            "SELECT * FROM character_state_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

    def get_state_snapshot_values(self, snapshot_id: str) -> dict[str, int]:
        require_text(snapshot_id, "snapshot_id")
        rows = self._connection.execute(
            """
            SELECT variable_name, variable_value
            FROM character_state_snapshot_values
            WHERE snapshot_id = ?
            ORDER BY variable_name
            """,
            (snapshot_id,),
        ).fetchall()
        return {row["variable_name"]: row["variable_value"] for row in rows}

    def get_latest_state_snapshot(self, run_id: str) -> sqlite3.Row | None:
        require_text(run_id, "run_id")
        return self._connection.execute(
            """
            SELECT snapshot.*
            FROM character_state_snapshots AS snapshot
            WHERE snapshot.run_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM character_state_snapshots AS child
                  WHERE child.previous_snapshot_id = snapshot.snapshot_id
              )
            """,
            (run_id,),
        ).fetchone()


    def get_current_state_snapshot(self, run_id: str) -> sqlite3.Row | None:
        """Return the unique current head; reject a forked state history."""
        require_text(run_id, "run_id")

        rows = self._connection.execute(
            """
            SELECT snapshot.*
            FROM character_state_snapshots AS snapshot
            WHERE snapshot.run_id = ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM character_state_snapshots AS child
                  WHERE child.previous_snapshot_id = snapshot.snapshot_id
              )
            """,
            (run_id,),
        ).fetchall()

        if len(rows) > 1:
            raise ValueError("Character state history has multiple current heads.")

        return rows[0] if rows else None

    def get_state_transition(self, transition_id: str) -> sqlite3.Row | None:
        require_text(transition_id, "transition_id")
        return self._connection.execute(
            """
            SELECT *
            FROM character_state_transitions
            WHERE transition_id = ?
            """,
            (transition_id,),
        ).fetchone()

    def get_state_transition_by_idempotency_key(
        self,
        run_id: str,
        idempotency_key: str,
    ) -> sqlite3.Row | None:
        require_text(run_id, "run_id")
        require_text(idempotency_key, "idempotency_key")
        return self._connection.execute(
            """
            SELECT *
            FROM character_state_transitions
            WHERE run_id = ? AND idempotency_key = ?
            """,
            (run_id, idempotency_key),
        ).fetchone()

    def get_state_transition_evidence(
        self,
        transition_id: str,
    ) -> list[sqlite3.Row]:
        require_text(transition_id, "transition_id")
        return list(
            self._connection.execute(
                """
                SELECT *
                FROM character_state_transition_evidence
                WHERE transition_id = ?
                ORDER BY message_id
                """,
                (transition_id,),
            ).fetchall()
        )

    def create_state_transition(
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
        confidence: float | None = None,
        uncertainty_notes: str | None = None,
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

        if variable_name not in CHARACTER_STATE_BOUNDS:
            raise ValueError("Unknown character-state variable.")

        minimum, maximum = CHARACTER_STATE_BOUNDS[variable_name]

        for name, value in (
            ("previous_value", previous_value),
            ("proposed_value", proposed_value),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise ValueError(f"{name} is outside the allowed bounds.")

        if validation_status not in {"pending", "requires_review"}:
            raise ValueError("New transitions must remain unaccepted.")

        if confidence is not None:
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0.0 <= confidence <= 1.0
            ):
                raise ValueError("Transition confidence must be between 0 and 1.")

        if uncertainty_notes is not None:
            require_text(uncertainty_notes, "uncertainty_notes")

        require_session_for_run(self._connection, session_id, run_id)

        self._connection.execute(
            """
            INSERT INTO character_state_transitions (
                transition_id,
                run_id,
                session_id,
                event_id,
                variable_name,
                previous_value,
                proposed_value,
                accepted_value,
                validation_status,
                confidence,
                uncertainty_notes,
                idempotency_key,
                created_at,
                validated_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL)
            """,
            (
                transition_id,
                run_id,
                session_id,
                variable_name,
                previous_value,
                proposed_value,
                validation_status,
                confidence,
                uncertainty_notes,
                idempotency_key,
                created_at,
            ),
        )

    def add_state_transition_evidence(
        self,
        transition_id: str,
        message_id: str,
        evidence_role: str,
        relevance_note: str | None = None,
    ) -> None:
        for name, value in (
            ("transition_id", transition_id),
            ("message_id", message_id),
            ("evidence_role", evidence_role),
        ):
            require_text(value, name)

        if relevance_note is not None:
            require_text(relevance_note, "relevance_note")

        self._connection.execute(
            """
            INSERT INTO character_state_transition_evidence (
                transition_id,
                message_id,
                evidence_role,
                relevance_note
            )
            VALUES (?, ?, ?, ?)
            """,
            (transition_id, message_id, evidence_role, relevance_note),
        )

    def resolve_state_transition(
        self,
        transition_id: str,
        *,
        validation_status: str,
        validated_at: str,
        accepted_value: int | None = None,
    ) -> bool:
        require_text(transition_id, "transition_id")
        require_text(validated_at, "validated_at")

        if validation_status not in {"accepted", "rejected"}:
            raise ValueError("A transition can only be accepted or rejected.")

        if validation_status == "accepted":
            row = self.get_state_transition(transition_id)
            if row is None:
                raise ValueError("Transition does not exist.")

            bounds = CHARACTER_STATE_BOUNDS[row["variable_name"]]
            if (
                isinstance(accepted_value, bool)
                or not isinstance(accepted_value, int)
                or not bounds[0] <= accepted_value <= bounds[1]
            ):
                raise ValueError("Accepted value is outside the allowed bounds.")
        elif accepted_value is not None:
            raise ValueError("Rejected transitions cannot have an accepted value.")

        cursor = self._connection.execute(
            """
            UPDATE character_state_transitions
            SET validation_status = ?,
                accepted_value = ?,
                validated_at = ?
            WHERE transition_id = ?
              AND validation_status IN ('pending', 'requires_review')
            """,
            (
                validation_status,
                accepted_value,
                validated_at,
                transition_id,
            ),
        )

        return cursor.rowcount == 1
