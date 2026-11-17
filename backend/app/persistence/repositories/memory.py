"""Repository for versioned longitudinal memory records."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    require_message_for_run,
    require_offsets,
    require_session_for_run,
    require_text,
)


MEMORY_INFORMATION_CLASSES = {
    "confirmed_fact",
    "explicit_disclosure",
    "therapist_hypothesis",
    "system_generated_summary",
    "reported_outcome",
    "structured_observation",
}
MEMORY_STATUSES = {"active", "superseded", "requires_review", "rejected"}


MEMORY_SCOPES = frozenset({
    "legacy_unclassified",
    "episodic",
    "semantic",
    "therapeutic",
})


class MemoryRepository(ConnectionBoundRepository):
    """Stores selected memory and links it to original transcript evidence."""

    def get(self, memory_id: str) -> sqlite3.Row | None:
        self.require_text(memory_id, "memory_id")
        return self._connection.execute(
            "SELECT * FROM memory_items WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()

    def create_memory(
        self,
        *,
        memory_id: str,
        run_id: str,
        memory_type: str,
        information_class: str,
        content: str,
        memory_version: int,
        created_at: str,
        updated_at: str,
        status: str = "active",
        confidence: float | None = None,
        source_session_id: str | None = None,
        memory_scope: str = "legacy_unclassified",
        supersedes_memory_id: str | None = None,
        origin_interaction_request_id: str | None = None,
        proposal_index: int | None = None,
    ) -> None:
        for name, value in (
            ("memory_id", memory_id),
            ("run_id", run_id),
            ("memory_type", memory_type),
            ("information_class", information_class),
            ("content", content),
            ("created_at", created_at),
            ("updated_at", updated_at),
        ):
            require_text(value, name)

        if information_class not in MEMORY_INFORMATION_CLASSES:
            raise ValueError("Invalid memory information class.")

        if status not in MEMORY_STATUSES:
            raise ValueError("Invalid memory status.")

        if not isinstance(memory_scope, str) or memory_scope not in MEMORY_SCOPES:
            raise ValueError("Invalid memory scope.")

        if isinstance(memory_version, bool) or not isinstance(memory_version, int) or memory_version < 1:
            raise ValueError("Memory version must be a positive integer.")

        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (float, int)) or not 0.0 <= confidence <= 1.0:
                raise ValueError("Memory confidence must be between 0 and 1.")

        if supersedes_memory_id is not None:
            require_text(supersedes_memory_id, "supersedes_memory_id")

        if origin_interaction_request_id is not None:
            require_text(
                origin_interaction_request_id,
                "origin_interaction_request_id",
            )

        if proposal_index is not None and (
            isinstance(proposal_index, bool)
            or not isinstance(proposal_index, int)
            or proposal_index < 0
        ):
            raise ValueError("Proposal index must be a non-negative integer.")

        if source_session_id is not None:
            require_session_for_run(
                self._connection,
                source_session_id,
                run_id,
            )

        if (origin_interaction_request_id is None) != (proposal_index is None):
            raise ValueError(
                "Origin interaction and proposal index must be supplied together."
            )
        if origin_interaction_request_id is not None:
            request = self._connection.execute(
                """
                SELECT session_id
                FROM interaction_requests
                WHERE request_id = ?
                """,
                (origin_interaction_request_id,),
            ).fetchone()
            if request is None or request["session_id"] != source_session_id:
                raise ValueError(
                    "Memory origin interaction must match its source session."
                )

        if supersedes_memory_id is not None:
            previous = self.get(supersedes_memory_id)
            if previous is None or previous["run_id"] != run_id:
                raise ValueError(
                    "A superseded memory must belong to the same Run."
                )
            if memory_version != previous["memory_version"] + 1:
                raise ValueError(
                    "A superseding memory version must increment by one."
                )

        self._connection.execute(
            """
            INSERT INTO memory_items (
                memory_id, run_id, source_session_id,
                memory_type, information_class, content,
                confidence, status, memory_version, memory_scope,
                supersedes_memory_id, origin_interaction_request_id,
                proposal_index, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                run_id,
                source_session_id,
                memory_type,
                information_class,
                content,
                confidence,
                status,
                memory_version,
                memory_scope,
                supersedes_memory_id,
                origin_interaction_request_id,
                proposal_index,
                created_at,
                updated_at,
            ),
        )

    def get_by_origin(
        self,
        interaction_request_id: str,
        proposal_index: int,
    ) -> sqlite3.Row | None:
        require_text(interaction_request_id, "interaction_request_id")
        if isinstance(proposal_index, bool) or not isinstance(proposal_index, int) or proposal_index < 0:
            raise ValueError("Proposal index must be a non-negative integer.")
        return self._connection.execute(
            """
            SELECT * FROM memory_items
            WHERE origin_interaction_request_id = ?
              AND proposal_index = ?
            """,
            (interaction_request_id, proposal_index),
        ).fetchone()

    def update_status(
        self,
        memory_id: str,
        *,
        expected_status: str,
        status: str,
        updated_at: str,
    ) -> bool:
        require_text(memory_id, "memory_id")
        require_text(updated_at, "updated_at")
        if expected_status not in MEMORY_STATUSES or status not in MEMORY_STATUSES:
            raise ValueError("Invalid memory status.")

        allowed_transitions = {
            ("requires_review", "active"),
            ("requires_review", "rejected"),
            ("active", "superseded"),
        }
        if (expected_status, status) not in allowed_transitions:
            raise ValueError("Invalid memory status transition.")

        cursor = self._connection.execute(
            """
            UPDATE memory_items
            SET status = ?, updated_at = ?
            WHERE memory_id = ? AND status = ?
            """,
            (status, updated_at, memory_id, expected_status),
        )
        return cursor.rowcount == 1

    def add_evidence(
        self,
        memory_id: str,
        message_id: str,
        relationship_type: str,
        *,
        start_offset: int | None = None,
        end_offset: int | None = None,
    ) -> bool:
        for name, value in (
            ("memory_id", memory_id),
            ("message_id", message_id),
            ("relationship_type", relationship_type),
        ):
            require_text(value, name)

        memory = self.get(memory_id)
        if memory is None:
            raise ValueError("Memory item does not exist.")

        message = require_message_for_run(
            self._connection,
            message_id,
            memory["run_id"],
        )
        require_offsets(message["content"], start_offset, end_offset)

        existing = self._connection.execute(
            """
            SELECT relationship_type, start_offset, end_offset
            FROM memory_evidence
            WHERE memory_id = ? AND message_id = ?
            """,
            (memory_id, message_id),
        ).fetchone()

        if existing is not None:
            if (
                existing["relationship_type"],
                existing["start_offset"],
                existing["end_offset"],
            ) == (relationship_type, start_offset, end_offset):
                return False
            raise ValueError("Memory evidence already exists with another relationship.")

        self._connection.execute(
            """
            INSERT INTO memory_evidence (
                memory_id, message_id, relationship_type,
                start_offset, end_offset
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                message_id,
                relationship_type,
                start_offset,
                end_offset,
            ),
        )
        return True

    def create_review(
        self,
        *,
        review_id: str,
        memory_id: str,
        decision: str,
        reviewer_id: str,
        rationale: str,
        reviewed_at: str,
    ) -> None:
        for name, value in (
            ("review_id", review_id),
            ("memory_id", memory_id),
            ("reviewer_id", reviewer_id),
            ("rationale", rationale),
            ("reviewed_at", reviewed_at),
        ):
            require_text(value, name)
        if decision not in {"accepted", "rejected"}:
            raise ValueError("Invalid memory review decision.")

        self._connection.execute(
            """
            INSERT INTO memory_reviews (
                review_id, memory_id, decision,
                reviewer_id, rationale, reviewed_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                memory_id,
                decision,
                reviewer_id,
                rationale,
                reviewed_at,
            ),
        )

    def get_review(self, memory_id: str) -> sqlite3.Row | None:
        self.require_text(memory_id, "memory_id")
        return self._connection.execute(
            "SELECT * FROM memory_reviews WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()

    def list_by_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
    ) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")

        if status is not None and status not in MEMORY_STATUSES:
            raise ValueError("Invalid memory status.")

        if status is None:
            query = """
                SELECT * FROM memory_items
                WHERE run_id = ?
                ORDER BY created_at, memory_id
            """
            params = (run_id,)
        else:
            query = """
                SELECT * FROM memory_items
                WHERE run_id = ? AND status = ?
                ORDER BY created_at, memory_id
            """
            params = (run_id, status)

        return list(self._connection.execute(query, params).fetchall())

    def list_evidence(self, memory_id: str) -> list[sqlite3.Row]:
        self.require_text(memory_id, "memory_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM memory_evidence
                WHERE memory_id = ?
                ORDER BY message_id
                """,
                (memory_id,),
            ).fetchall()
        )

    def list_active_for_consolidation(self, run_id: str) -> list[sqlite3.Row]:
        self.require_text(run_id, "run_id")
        return list(
            self._connection.execute(
                """
                SELECT memory_items.*, sessions.session_number
                FROM memory_items
                JOIN sessions
                  ON sessions.session_id = memory_items.source_session_id
                 AND sessions.run_id = memory_items.run_id
                WHERE memory_items.run_id = ?
                  AND memory_items.status = 'active'
                  AND memory_items.source_session_id IS NOT NULL
                ORDER BY sessions.session_number, memory_items.created_at,
                         memory_items.memory_id
                """,
                (run_id,),
            ).fetchall()
        )

    def create_consolidation_source(
        self,
        *,
        consolidated_memory_id: str,
        source_memory_id: str,
        source_memory_version: int,
        source_session_id: str,
        source_content: str,
        relationship_type: str,
        created_at: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO memory_consolidation_sources(
                consolidated_memory_id, source_memory_id,
                source_memory_version, source_session_id, source_content,
                relationship_type, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consolidated_memory_id,
                source_memory_id,
                source_memory_version,
                source_session_id,
                source_content,
                relationship_type,
                created_at,
            ),
        )

    def list_consolidation_sources(
        self,
        consolidated_memory_id: str,
    ) -> list[sqlite3.Row]:
        self.require_text(consolidated_memory_id, "memory_id")
        return list(
            self._connection.execute(
                """
                SELECT sources.source_memory_id, sources.source_memory_version,
                       sources.relationship_type,
                       sources.source_content AS content,
                       sources.source_session_id
                FROM memory_consolidation_sources AS sources
                WHERE sources.consolidated_memory_id = ?
                ORDER BY sources.source_memory_id
                """,
                (consolidated_memory_id,),
            ).fetchall()
        )
