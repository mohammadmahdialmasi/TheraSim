"""Repository for run-specific case-fact disclosure tracking."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    require_message_for_run,
    require_offsets,
    require_text,
)


DISCLOSURE_STATUSES = {
    "not_disclosed",
    "candidate_disclosed",
    "confirmed_disclosed",
    "requires_review",
}


class DisclosureRepository(ConnectionBoundRepository):
    """Stores disclosure metadata only; hidden fact content stays in case_vault."""

    def get(self, disclosure_id: str) -> sqlite3.Row | None:
        self.require_text(disclosure_id, "disclosure_id")
        return self._connection.execute(
            "SELECT * FROM case_fact_disclosures WHERE disclosure_id = ?",
            (disclosure_id,),
        ).fetchone()

    def get_by_fact(
        self,
        run_id: str,
        case_fact_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(run_id, "run_id")
        self.require_text(case_fact_id, "case_fact_id")
        return self._connection.execute(
            """
            SELECT * FROM case_fact_disclosures
            WHERE run_id = ? AND case_fact_id = ?
            """,
            (run_id, case_fact_id),
        ).fetchone()

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM case_fact_disclosures
                WHERE run_id = ?
                ORDER BY created_at, disclosure_id
                """,
                (run_id,),
            ).fetchall()
        )

    def create_disclosure(
        self,
        *,
        disclosure_id: str,
        run_id: str,
        case_id: str,
        case_version_id: str,
        case_fact_id: str,
        created_at: str,
        operation_id: str,
        validation_method: str = "initialization",
        disclosure_status: str = "not_disclosed",
        source_message_id: str | None = None,
        evidence_start_offset: int | None = None,
        evidence_end_offset: int | None = None,
        validation_notes: str | None = None,
        evidence_description: str | None = None,
    ) -> None:
        for name, value in (
            ("disclosure_id", disclosure_id),
            ("run_id", run_id),
            ("case_id", case_id),
            ("case_version_id", case_version_id),
            ("case_fact_id", case_fact_id),
            ("created_at", created_at),
            ("operation_id", operation_id),
            ("validation_method", validation_method),
        ):
            require_text(value, name)

        if disclosure_status not in DISCLOSURE_STATUSES:
            raise ValueError("Invalid disclosure status.")

        run = self._connection.execute(
            """
            SELECT case_id, case_version_id
            FROM simulation_runs WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

        if run is None or (
            run["case_id"], run["case_version_id"]
        ) != (case_id, case_version_id):
            raise ValueError("Disclosure case identity does not match its run.")

        if source_message_id is not None:
            message = require_message_for_run(
                self._connection,
                source_message_id,
                run_id,
                role="patient",
            )
            require_offsets(
                message["content"],
                evidence_start_offset,
                evidence_end_offset,
            )
        elif evidence_start_offset is not None or evidence_end_offset is not None:
            raise ValueError("Evidence offsets require a source message.")

        if disclosure_status == "confirmed_disclosed" and source_message_id is None:
            raise ValueError("Confirmed disclosure requires a patient message.")

        self._connection.execute(
            """
            INSERT INTO case_fact_disclosures (
                disclosure_id, run_id, case_id, case_version_id,
                case_fact_id, disclosure_status, source_message_id,
                evidence_start_offset, evidence_end_offset,
                validation_method, validation_notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                disclosure_id,
                run_id,
                case_id,
                case_version_id,
                case_fact_id,
                disclosure_status,
                source_message_id,
                evidence_start_offset,
                evidence_end_offset,
                validation_method,
                validation_notes,
                created_at,
                created_at,
            ),
        )

        self._connection.execute(
            """
            INSERT INTO case_fact_disclosure_history (
                history_id, disclosure_id, previous_status,
                new_status, source_message_id, evidence_description,
                operation_id, created_at
            )
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                f"history:{operation_id}",
                disclosure_id,
                disclosure_status,
                source_message_id,
                evidence_description,
                operation_id,
                created_at,
            ),
        )

    def update_status(
        self,
        disclosure_id: str,
        new_status: str,
        *,
        operation_id: str,
        created_at: str,
        validation_method: str,
        source_message_id: str | None = None,
        evidence_start_offset: int | None = None,
        evidence_end_offset: int | None = None,
        validation_notes: str | None = None,
        evidence_description: str | None = None,
    ) -> bool:
        require_text(disclosure_id, "disclosure_id")
        require_text(operation_id, "operation_id")
        require_text(created_at, "created_at")
        require_text(validation_method, "validation_method")

        if new_status not in DISCLOSURE_STATUSES:
            raise ValueError("Invalid disclosure status.")

        existing_operation = self._connection.execute(
            """
            SELECT disclosure_id, new_status
            FROM case_fact_disclosure_history
            WHERE operation_id = ?
            """,
            (operation_id,),
        ).fetchone()

        if existing_operation is not None:
            if (
                existing_operation["disclosure_id"] == disclosure_id
                and existing_operation["new_status"] == new_status
            ):
                return False
            raise ValueError("Disclosure operation ID was reused.")

        current = self.get(disclosure_id)
        if current is None:
            raise ValueError("Disclosure record does not exist.")

        run_id = current["run_id"]
        source = source_message_id or current["source_message_id"]

        if source_message_id is not None:
            message = require_message_for_run(
                self._connection,
                source_message_id,
                run_id,
                role="patient",
            )
            require_offsets(
                message["content"],
                evidence_start_offset,
                evidence_end_offset,
            )
        elif evidence_start_offset is not None or evidence_end_offset is not None:
            raise ValueError("Evidence offsets require a source message.")

        if new_status == "confirmed_disclosed" and source is None:
            raise ValueError("Confirmed disclosure requires validated evidence.")

        if new_status == current["disclosure_status"]:
            return False

        self._connection.execute(
            """
            UPDATE case_fact_disclosures
            SET disclosure_status = ?,
                source_message_id = ?,
                evidence_start_offset = ?,
                evidence_end_offset = ?,
                validation_method = ?,
                validation_notes = ?,
                updated_at = ?
            WHERE disclosure_id = ?
            """,
            (
                new_status,
                source,
                evidence_start_offset if source_message_id else current["evidence_start_offset"],
                evidence_end_offset if source_message_id else current["evidence_end_offset"],
                validation_method,
                validation_notes,
                created_at,
                disclosure_id,
            ),
        )

        self._connection.execute(
            """
            INSERT INTO case_fact_disclosure_history (
                history_id, disclosure_id, previous_status, new_status,
                source_message_id, evidence_description, operation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"history:{operation_id}",
                disclosure_id,
                current["disclosure_status"],
                new_status,
                source,
                evidence_description,
                operation_id,
                created_at,
            ),
        )

        return True

    def list_history(self, disclosure_id: str) -> list[sqlite3.Row]:
        self.require_text(disclosure_id, "disclosure_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM case_fact_disclosure_history
                WHERE disclosure_id = ?
                ORDER BY created_at, history_id
                """,
                (disclosure_id,),
            ).fetchall()
        )
