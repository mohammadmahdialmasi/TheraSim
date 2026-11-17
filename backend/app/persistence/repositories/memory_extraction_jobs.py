"""Durable, leased outbox for post-interaction memory extraction."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.character_runtime import RunCharacterRepository


class MemoryExtractionJobRepository(ConnectionBoundRepository):
    """Enqueue and lease memory-extraction jobs without holding model calls."""

    def enqueue(
        self,
        *,
        job_id: str,
        run_id: str,
        session_id: str,
        interaction_request_id: str,
        created_at: str,
    ) -> sqlite3.Row:
        for name, value in (
            ("job_id", job_id),
            ("run_id", run_id),
            ("session_id", session_id),
            ("interaction_request_id", interaction_request_id),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        interaction = self._connection.execute(
            """
            SELECT r.processing_status, s.run_id, s.session_id
            FROM interaction_requests AS r
            JOIN sessions AS s ON s.session_id = r.session_id
            WHERE r.request_id = ?
            """,
            (interaction_request_id,),
        ).fetchone()
        if (
            interaction is None
            or interaction["processing_status"] != "completed"
            or interaction["run_id"] != run_id
            or interaction["session_id"] != session_id
        ):
            raise ValueError(
                "Memory extraction jobs require a completed interaction "
                "in the same Run and session."
            )

        existing = self.get_by_interaction(interaction_request_id)
        if existing is not None:
            if (
                existing["run_id"] == run_id
                and existing["session_id"] == session_id
            ):
                return existing
            raise ValueError(
                "An interaction request is already linked to another job."
            )

        character_state_snapshot = (
            RunCharacterRepository(self._connection)
            .get_current_state_snapshot(run_id)
        )

        self._connection.execute(
            """
            INSERT INTO memory_extraction_jobs (
                job_id, run_id, session_id, interaction_request_id,
                status, attempt_count, candidate_count, available_at,
                character_state_snapshot_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'pending', 0, 0, ?, ?, ?, ?)
            """,
            (
                job_id,
                run_id,
                session_id,
                interaction_request_id,
                created_at,
                (
                    character_state_snapshot["snapshot_id"]
                    if character_state_snapshot is not None
                    else None
                ),
                created_at,
                created_at,
            ),
        )
        row = self.get_by_interaction(interaction_request_id)
        if row is None:
            raise RuntimeError("Enqueued memory extraction job disappeared.")
        return row

    def get_by_interaction(
        self,
        interaction_request_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(interaction_request_id, "interaction_request_id")
        return self._connection.execute(
            """
            SELECT * FROM memory_extraction_jobs
            WHERE interaction_request_id = ?
            """,
            (interaction_request_id,),
        ).fetchone()

    def claim_next(
        self,
        *,
        worker_id: str,
        now: str,
        lease_expires_at: str,
        max_attempts: int,
    ) -> sqlite3.Row | None:
        self.require_text(worker_id, "worker_id")
        self.require_text(now, "now")
        self.require_text(lease_expires_at, "lease_expires_at")
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer.")

        self._connection.execute(
            """
            UPDATE model_runs
            SET execution_status = 'failed',
                completed_at = ?,
                output_validation_status = 'not_validated'
            WHERE execution_status = 'in_progress'
              AND model_run_id IN (
                    SELECT model_run_id
                    FROM memory_extraction_jobs
                    WHERE status = 'processing'
                      AND attempt_count >= ?
                      AND julianday(lease_expires_at) <= julianday(?)
                      AND model_run_id IS NOT NULL
              )
            """,
            (now, max_attempts, now),
        )
        self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET status = 'failed',
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error_code = 'worker_lease_expired',
                updated_at = ?
            WHERE status = 'processing'
              AND attempt_count >= ?
              AND julianday(lease_expires_at) <= julianday(?)
            """,
            (now, max_attempts, now),
        )
        job = self._connection.execute(
            """
            SELECT * FROM memory_extraction_jobs
            WHERE attempt_count < ?
              AND (
                    (
                        status = 'pending'
                        AND julianday(available_at) <= julianday(?)
                    )
                    OR
                    (
                        status = 'processing'
                        AND julianday(lease_expires_at) <= julianday(?)
                    )
              )
            ORDER BY created_at, job_id
            LIMIT 1
            """,
            (max_attempts, now, now),
        ).fetchone()
        if job is None:
            return None

        cursor = self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET status = 'processing',
                attempt_count = attempt_count + 1,
                lease_owner = ?,
                lease_expires_at = ?,
                last_error_code = NULL,
                updated_at = ?
            WHERE job_id = ?
              AND attempt_count = ?
              AND (
                    status = 'pending'
                    OR (
                        status = 'processing'
                        AND julianday(lease_expires_at) <= julianday(?)
                    )
              )
            """,
            (
                worker_id,
                lease_expires_at,
                now,
                job["job_id"],
                job["attempt_count"],
                now,
            ),
        )
        if cursor.rowcount != 1:
            return None
        return self._connection.execute(
            "SELECT * FROM memory_extraction_jobs WHERE job_id = ?",
            (job["job_id"],),
        ).fetchone()

    def mark_completed(
        self,
        job_id: str,
        *,
        worker_id: str,
        candidate_count: int,
        completed_at: str,
    ) -> bool:
        self.require_text(job_id, "job_id")
        self.require_text(worker_id, "worker_id")
        self.require_text(completed_at, "completed_at")
        if (
            isinstance(candidate_count, bool)
            or not isinstance(candidate_count, int)
            or candidate_count < 0
        ):
            raise ValueError("candidate_count must be a non-negative integer.")

        cursor = self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET status = 'completed',
                candidate_count = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error_code = NULL,
                updated_at = ?,
                completed_at = ?
            WHERE job_id = ?
              AND status = 'processing'
              AND lease_owner = ?
              AND proposal_payload IS NOT NULL
              AND output_hash IS NOT NULL
            """,
            (
                candidate_count,
                completed_at,
                completed_at,
                job_id,
                worker_id,
            ),
        )
        return cursor.rowcount == 1

    def save_proposals(
        self,
        job_id: str,
        *,
        worker_id: str,
        proposal_payload: str,
        output_hash: str,
        updated_at: str,
    ) -> bool:
        for name, value in (
            ("job_id", job_id),
            ("worker_id", worker_id),
            ("proposal_payload", proposal_payload),
            ("output_hash", output_hash),
            ("updated_at", updated_at),
        ):
            self.require_text(value, name)
        job = self._connection.execute(
            "SELECT status, lease_owner, proposal_payload, output_hash "
            "FROM memory_extraction_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if (
            job is None
            or job["status"] != "processing"
            or job["lease_owner"] != worker_id
        ):
            return False
        if job["proposal_payload"] is not None:
            if (
                job["proposal_payload"] == proposal_payload
                and job["output_hash"] == output_hash
            ):
                return True
            raise ValueError(
                "A memory extraction job cannot replace its saved proposals."
            )
        cursor = self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET proposal_payload = ?, output_hash = ?, updated_at = ?
            WHERE job_id = ?
              AND status = 'processing'
              AND lease_owner = ?
              AND proposal_payload IS NULL
              AND output_hash IS NULL
            """,
            (
                proposal_payload,
                output_hash,
                updated_at,
                job_id,
                worker_id,
            ),
        )
        return cursor.rowcount == 1

    def set_model_run(
        self,
        job_id: str,
        *,
        worker_id: str,
        model_run_id: str,
        updated_at: str,
    ) -> bool:
        for name, value in (
            ("job_id", job_id),
            ("worker_id", worker_id),
            ("model_run_id", model_run_id),
            ("updated_at", updated_at),
        ):
            self.require_text(value, name)
        cursor = self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET model_run_id = ?, updated_at = ?
            WHERE job_id = ?
              AND status = 'processing'
              AND lease_owner = ?
              AND proposal_payload IS NULL
            """,
            (model_run_id, updated_at, job_id, worker_id),
        )
        return cursor.rowcount == 1

    def mark_failed(
        self,
        job_id: str,
        *,
        worker_id: str,
        error_code: str,
        retry_at: str,
        failed_at: str,
        max_attempts: int,
        retryable: bool,
    ) -> bool:
        for name, value in (
            ("job_id", job_id),
            ("worker_id", worker_id),
            ("error_code", error_code),
            ("retry_at", retry_at),
            ("failed_at", failed_at),
        ):
            self.require_text(value, name)
        if (
            isinstance(max_attempts, bool)
            or not isinstance(max_attempts, int)
            or max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer.")
        if not isinstance(retryable, bool):
            raise TypeError("retryable must be a boolean.")

        cursor = self._connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET status = CASE
                    WHEN attempt_count >= ? OR ? = 0 THEN 'failed'
                    ELSE 'pending'
                END,
                available_at = ?,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error_code = ?,
                updated_at = ?
            WHERE job_id = ?
              AND status = 'processing'
              AND lease_owner = ?
            """,
            (
                max_attempts,
                int(retryable),
                retry_at,
                error_code,
                failed_at,
                job_id,
                worker_id,
            ),
        )
        return cursor.rowcount == 1
