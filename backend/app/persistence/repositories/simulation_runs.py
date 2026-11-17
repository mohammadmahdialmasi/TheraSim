"""Repository for longitudinal simulation runs."""

import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository


RUN_STATUSES = {
    "initialized",
    "active",
    "completed",
    "interrupted",
    "failed",
}

SESSION_PLANNING_POLICIES = {
    "flexible",
    "goal_based",
    "milestone_based",
    "open_ended",
}


class SimulationRunRepository(ConnectionBoundRepository):
    """Stores simulation-run metadata without owning transactions."""

    def create_run(
        self,
        *,
        run_id: str,
        case_id: str,
        case_version_id: str,
        modality: str,
        language: str,
        configuration_version: str,
        created_at: str,
        protocol_id: str = "ACT_EDUCATIONAL_SIMULATION",
        protocol_version: str = "0.1",
        session_planning_policy: str = "flexible",
        evaluation_rubric_id: str = "ACT_RUBRIC_V0",
        evaluation_rubric_version: str = "0.2",
        status: str = "initialized",
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> None:
        for name, value in (
            ("run_id", run_id),
            ("case_id", case_id),
            ("case_version_id", case_version_id),
            ("modality", modality),
            ("language", language),
            ("configuration_version", configuration_version),
            ("created_at", created_at),
            ("protocol_id", protocol_id),
            ("protocol_version", protocol_version),
            ("evaluation_rubric_id", evaluation_rubric_id),
            ("evaluation_rubric_version", evaluation_rubric_version),
        ):
            self.require_text(value, name)

        if status not in RUN_STATUSES:
            raise ValueError("Invalid simulation run status.")
        if session_planning_policy not in SESSION_PLANNING_POLICIES:
            raise ValueError("Invalid session planning policy.")

        self._connection.execute(
            """
            INSERT INTO simulation_runs (
                run_id, case_id, case_version_id,
                modality, language, status,
                configuration_version, started_at,
                completed_at, created_at, protocol_id, protocol_version,
                session_planning_policy, evaluation_rubric_id,
                evaluation_rubric_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                case_id,
                case_version_id,
                modality,
                language,
                status,
                configuration_version,
                started_at,
                completed_at,
                created_at,
                protocol_id,
                protocol_version,
                session_planning_policy,
                evaluation_rubric_id,
                evaluation_rubric_version,
            ),
        )

    def get_run(self, run_id: str) -> sqlite3.Row | None:
        self.require_text(run_id, "run_id")

        return self._connection.execute(
            "SELECT * FROM simulation_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

    def list_runs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        self.require_pagination(limit, offset)

        if status is not None and status not in RUN_STATUSES:
            raise ValueError("Invalid simulation run status.")

        if status is None:
            cursor = self._connection.execute(
                """
                SELECT * FROM simulation_runs
                ORDER BY created_at DESC, run_id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            cursor = self._connection.execute(
                """
                SELECT * FROM simulation_runs
                WHERE status = ?
                ORDER BY created_at DESC, run_id
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset),
            )

        return list(cursor.fetchall())

    def update_status(
        self,
        run_id: str,
        status: str,
        *,
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> bool:
        self.require_text(run_id, "run_id")

        if status not in RUN_STATUSES:
            raise ValueError("Invalid simulation run status.")

        assignments = ["status = ?"]
        values: list[object] = [status]

        if started_at is not None:
            self.require_text(started_at, "started_at")
            assignments.append("started_at = ?")
            values.append(started_at)

        if completed_at is not None:
            self.require_text(completed_at, "completed_at")
            assignments.append("completed_at = ?")
            values.append(completed_at)

        values.append(run_id)

        cursor = self._connection.execute(
            f"""
            UPDATE simulation_runs
            SET {", ".join(assignments)}
            WHERE run_id = ?
            """,
            values,
        )

        return cursor.rowcount == 1
