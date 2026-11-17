"""Evaluation availability and read access for TheraSim reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from app.persistence.database import DatabaseManager

SESSION_COMPETENCIES = (
    "therapeutic_relationship",
    "functional_assessment",
    "psychological_workability",
    "acceptance_willingness",
    "cognitive_defusion",
    "present_moment_awareness",
    "values_clarification",
    "committed_action",
    "clinical_responsiveness",
    "safety_professional_boundaries",
)

LONGITUDINAL_COMPETENCIES = (
    "longitudinal_formulation_continuity",
    "disclosure_integration",
    "longitudinal_homework_followup",
    "longitudinal_adaptation",
    "longitudinal_act_process_continuity",
    "longitudinal_therapeutic_relationship",
    "nonlinear_change_responsiveness",
    "longitudinal_values_action",
    "longitudinal_safety_boundaries",
)


class EvaluationServiceError(Exception):
    """Base class for evaluation service errors."""


class EvaluationUnavailableError(EvaluationServiceError):
    """No genuine Evaluator Agent is configured for this installation."""


class EvaluationNotFoundError(EvaluationServiceError):
    """The requested evaluation is not present."""


class EvaluationRubricError(EvaluationServiceError):
    """The requested rubric or version is unsupported or invalid."""


class EvaluationSessionError(EvaluationServiceError):
    """The evaluated session is not eligible for an evaluation."""


class EvaluationRunError(EvaluationServiceError):
    """The evaluated run is not eligible for a longitudinal evaluation."""


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    evaluation_id: str
    run_id: str
    session_id: str | None
    evaluation_scope: str
    rubric_id: str
    rubric_version: str
    status: str
    created_at: str
    overall_summary: str | None


class EvaluationService:
    """Expose historical reports without synthesizing evaluator results."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        self._database_manager = database_manager

    @staticmethod
    def _raise_unavailable() -> NoReturn:
        raise EvaluationUnavailableError(
            "The Evaluator Agent is not implemented; ACT rubrics remain "
            "experimental and no evaluation was created."
        )

    def generate_session_evaluation(
        self,
        *,
        session_id: str,
        rubric_id: str = "ACT_RUBRIC_V0",
        rubric_version: str = "0.2",
    ) -> NoReturn:
        self._raise_unavailable()

    def generate_run_evaluation(
        self,
        *,
        run_id: str,
        rubric_id: str = "ACT_LONGITUDINAL_RUBRIC_V0",
        rubric_version: str = "0.2",
    ) -> NoReturn:
        self._raise_unavailable()

    def list_session_evaluations(self, *, session_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.session_id = ?
                ORDER BY e.created_at DESC, e.evaluation_id
                """,
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_run_evaluations(self, *, run_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.run_id = ?
                ORDER BY e.created_at DESC, e.evaluation_id
                """,
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_evaluation(self, *, evaluation_id: str) -> dict | None:
        with self._database_manager.connection("operational") as connection:
            row = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.evaluation_id = ?
                """,
                (evaluation_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_items(self, *, evaluation_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM evaluation_items
                WHERE evaluation_id = ?
                ORDER BY competency_id
                """,
                (evaluation_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_evidence_for_item(self, *, evaluation_item_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM evaluation_evidence
                WHERE evaluation_item_id = ?
                ORDER BY message_id
                """,
                (evaluation_item_id,),
            ).fetchall()
            return [dict(row) for row in rows]
