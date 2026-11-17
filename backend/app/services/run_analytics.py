"""Evidence-linked, non-clinical analytics over persisted Run records."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import TypedDict

from app.persistence.database import DatabaseManager
from app.services.evaluations import EvaluationService


class RunAnalyticsError(RuntimeError):
    """Base error for Run analytics operations."""


class RunAnalyticsNotFoundError(RunAnalyticsError):
    """The requested Run does not exist."""


class RunAnalyticsIntegrityError(RunAnalyticsError):
    """Persisted data required for an analytics snapshot is malformed."""


class CompetencyObservation(TypedDict):
    evaluation_id: str
    evaluation_revision: int
    evaluation_status: str
    session_id: str
    session_number: int
    rating_code: str
    confidence: str | None
    evidence_message_ids: list[str]
    review_decisions: list[dict[str, str]]


class MissingCompetencyObservation(TypedDict):
    session_id: str
    session_number: int
    reason: str


class CompetencyTrajectorySummary(TypedDict):
    observed_session_count: int
    evaluable_count: int
    non_evaluable_count: int
    missing_count: int
    evidence_coverage_rate: float | None
    confidence_distribution: dict[str, int]
    review_decision_counts: dict[str, int]
    raw_rating_code_change: dict[str, object] | None


class CompetencyTrajectory(TypedDict):
    rubric_id: str
    rubric_version: str
    rubric_version_id: str
    rubric_content_hash: str | None
    competency_id: str
    observations: list[CompetencyObservation]
    missing_completed_sessions: list[MissingCompetencyObservation]
    summary: CompetencyTrajectorySummary


@dataclass(frozen=True, slots=True)
class RunAnalyticsSnapshot:
    data_scope: str
    run_id: str
    generated_at: str
    time_range_start: str | None
    time_range_end: str | None
    sessions: tuple[dict[str, object], ...]
    events: tuple[dict[str, object], ...]
    event_counts: dict[str, int]
    memories: tuple[dict[str, object], ...]
    memory_counts: dict[str, int]
    state_transitions: tuple[dict[str, object], ...]
    transition_counts: dict[str, int]
    plan_revisions: tuple[dict[str, object], ...]
    current_plan: dict[str, object] | None
    evaluations: tuple[dict[str, object], ...]
    competency_trajectories: tuple[CompetencyTrajectory, ...]
    limitations: tuple[str, ...]


class RunAnalyticsService:
    """Builds a read-only Run snapshot with identifiers for source tracing."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        evaluation_service: EvaluationService,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        if not isinstance(evaluation_service, EvaluationService):
            raise TypeError("An EvaluationService instance is required.")
        self._database_manager = database_manager
        self._evaluation_service = evaluation_service

    @staticmethod
    def _counts(records: list[dict[str, object]], field: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in records:
            value = record.get(field)
            if isinstance(value, str):
                counts[value] = counts.get(value, 0) + 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _plan_goal_counts(payload: object) -> dict[str, int]:
        if not isinstance(payload, dict):
            raise RunAnalyticsIntegrityError(
                "The active treatment plan is malformed."
            )
        definition = payload.get("definition")
        goals = definition.get("goals") if isinstance(definition, dict) else None
        if not isinstance(goals, list):
            raise RunAnalyticsIntegrityError(
                "The active treatment plan has no valid goal list."
            )
        counts: dict[str, int] = {}
        for goal in goals:
            if not isinstance(goal, dict) or not isinstance(goal.get("status"), str):
                raise RunAnalyticsIntegrityError(
                    "The active treatment plan contains a malformed goal."
                )
            status = goal["status"]
            counts[status] = counts.get(status, 0) + 1
        return dict(sorted(counts.items()))

    def _competency_trajectories(
        self,
        *,
        run_id: str,
        sessions: list[dict[str, object]],
        evaluations: list[dict[str, object]],
    ) -> tuple[CompetencyTrajectory, ...]:
        session_numbers = {
            session["session_id"]: session["session_number"]
            for session in sessions
        }
        groups: dict[
            tuple[str, str, str, str, str | None],
            CompetencyTrajectory,
        ] = {}
        evaluated_sessions: dict[
            tuple[str, str, str, str | None], set[str]
        ] = {}
        sessions_with_evaluations: dict[
            tuple[str, str, str, str | None], set[str]
        ] = {}

        for evaluation in evaluations:
            if (
                evaluation["evaluation_scope"] != "session"
                or evaluation["run_id"] != run_id
                or evaluation["session_id"] not in session_numbers
            ):
                continue
            rubric_key = (
                evaluation["rubric_id"],
                evaluation["rubric_version"],
                evaluation["rubric_version_id"],
                evaluation["rubric_content_hash"],
            )
            sessions_with_evaluations.setdefault(rubric_key, set()).add(
                evaluation["session_id"]
            )
            if evaluation["status"] not in {"requires_review", "completed"}:
                continue
            evaluated_sessions.setdefault(rubric_key, set()).add(
                evaluation["session_id"]
            )
            for item in self._evaluation_service.list_items(
                evaluation_id=evaluation["evaluation_id"]
            ):
                competency_id = item["competency_id"]
                key = (*rubric_key, competency_id)
                group = groups.setdefault(
                    key,
                    {
                        "rubric_id": rubric_key[0],
                        "rubric_version": rubric_key[1],
                        "rubric_version_id": rubric_key[2],
                        "rubric_content_hash": rubric_key[3],
                        "competency_id": competency_id,
                        "observations": [],
                        "missing_completed_sessions": [],
                        "summary": {
                            "observed_session_count": 0,
                            "evaluable_count": 0,
                            "non_evaluable_count": 0,
                            "missing_count": 0,
                            "evidence_coverage_rate": None,
                            "confidence_distribution": {},
                            "review_decision_counts": {},
                            "raw_rating_code_change": None,
                        },
                    },
                )
                evidence = self._evaluation_service.list_evidence_for_item(
                    evaluation_item_id=item["evaluation_item_id"]
                )
                if any(
                    reference.get("session_id") != evaluation["session_id"]
                    for reference in evidence
                ):
                    raise RunAnalyticsIntegrityError(
                        "A competency observation references evidence "
                        "outside its session."
                    )
                confidence = self._competency_confidence(
                    evaluation, competency_id
                )
                reviews = self._evaluation_service.list_reviews(
                    evaluation_id=evaluation["evaluation_id"]
                )
                group["observations"].append(
                    {
                        "evaluation_id": evaluation["evaluation_id"],
                        "evaluation_revision": evaluation["evaluation_revision"],
                        "evaluation_status": evaluation["status"],
                        "session_id": evaluation["session_id"],
                        "session_number": session_numbers[evaluation["session_id"]],
                        "rating_code": item["rating_code"],
                        "confidence": confidence,
                        "evidence_message_ids": [
                            reference["message_id"] for reference in evidence
                        ],
                        "review_decisions": [
                            {
                                "review_id": review["review_id"],
                                "reviewer_user_id": review["reviewer_user_id"],
                                "decision": review["decision"],
                                "created_at": review["created_at"],
                            }
                            for review in reviews
                        ],
                    }
                )

        trajectories: list[CompetencyTrajectory] = []
        completed_sessions = [
            session
            for session in sessions
            if session["status"] == "completed"
        ]
        for key, group in sorted(groups.items()):
            rubric_key = (key[0], key[1], key[2], key[3])
            rubric_sessions = evaluated_sessions[rubric_key]
            recorded_sessions = sessions_with_evaluations[rubric_key]
            observed_sessions = {
                observation["session_id"]
                for observation in group["observations"]
            }
            group["observations"].sort(
                key=lambda observation: (
                    observation["session_number"],
                    observation["evaluation_revision"],
                )
            )
            group["missing_completed_sessions"] = [
                {
                    "session_id": session["session_id"],
                    "session_number": session["session_number"],
                    "reason": (
                        "competency_not_reported"
                        if session["session_id"] in rubric_sessions
                        else (
                            "evaluation_not_reportable"
                            if session["session_id"] in recorded_sessions
                            else "no_evaluation_for_rubric"
                        )
                    ),
                }
                for session in completed_sessions
                if session["session_id"] not in observed_sessions
            ]
            latest_observation_by_session: dict[str, CompetencyObservation] = {}
            for observation in group["observations"]:
                latest_observation_by_session[observation["session_id"]] = observation
            latest_observations = sorted(
                latest_observation_by_session.values(),
                key=lambda observation: observation["session_number"],
            )
            evaluable = [
                observation
                for observation in latest_observations
                if observation["rating_code"] != "NE"
            ]
            evidence_observation_count = sum(
                bool(observation["evidence_message_ids"])
                for observation in evaluable
            )
            confidence_distribution: dict[str, int] = {}
            review_decision_counts: dict[str, int] = {}
            for observation in latest_observations:
                confidence = observation["confidence"]
                if confidence is not None:
                    confidence_distribution[confidence] = (
                        confidence_distribution.get(confidence, 0) + 1
                    )
                for review in observation["review_decisions"]:
                    decision = review["decision"]
                    review_decision_counts[decision] = (
                        review_decision_counts.get(decision, 0) + 1
                    )
            rating_change = None
            if len(evaluable) >= 2:
                first = evaluable[0]
                last = evaluable[-1]
                first_code = int(first["rating_code"])
                last_code = int(last["rating_code"])
                rating_change = {
                    "first_session_id": first["session_id"],
                    "first_session_number": first["session_number"],
                    "first_rating_code": first["rating_code"],
                    "last_session_id": last["session_id"],
                    "last_session_number": last["session_number"],
                    "last_rating_code": last["rating_code"],
                    "delta": last_code - first_code,
                }
            group["summary"] = {
                "observed_session_count": len(latest_observations),
                "evaluable_count": len(evaluable),
                "non_evaluable_count": sum(
                    observation["rating_code"] == "NE"
                    for observation in latest_observations
                ),
                "missing_count": len(group["missing_completed_sessions"]),
                "evidence_coverage_rate": (
                    evidence_observation_count / len(evaluable)
                    if evaluable
                    else None
                ),
                "confidence_distribution": dict(
                    sorted(confidence_distribution.items())
                ),
                "review_decision_counts": dict(
                    sorted(review_decision_counts.items())
                ),
                "raw_rating_code_change": rating_change,
            }
            trajectories.append(group)
        return tuple(trajectories)

    @staticmethod
    def _competency_confidence(
        evaluation: dict[str, object],
        competency_id: str,
    ) -> str | None:
        raw_metadata = evaluation.get("report_metadata")
        if raw_metadata is None:
            return None
        try:
            metadata = (
                json.loads(raw_metadata)
                if isinstance(raw_metadata, str)
                else raw_metadata
            )
        except json.JSONDecodeError:
            raise RunAnalyticsIntegrityError(
                "A session evaluation contains invalid report metadata."
            ) from None
        if not isinstance(metadata, dict):
            raise RunAnalyticsIntegrityError(
                "A session evaluation contains malformed report metadata."
            )
        competency_data = metadata.get("competencies")
        if competency_data is None:
            return None
        if not isinstance(competency_data, dict):
            raise RunAnalyticsIntegrityError(
                "A session evaluation contains malformed competency metadata."
            )
        item = competency_data.get(competency_id)
        if item is None:
            return None
        if not isinstance(item, dict):
            raise RunAnalyticsIntegrityError(
                "A session evaluation contains malformed competency metadata."
            )
        confidence = item.get("confidence")
        if confidence is None:
            return None
        if not isinstance(confidence, str) or confidence not in {
            "low",
            "medium",
            "high",
        }:
            raise RunAnalyticsIntegrityError(
                "A session evaluation contains invalid confidence metadata."
            )
        return confidence

    def get_snapshot(self, run_id: str) -> RunAnalyticsSnapshot:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be non-empty text.")
        with self._database_manager.connection("operational") as connection:
            if connection.execute(
                "SELECT 1 FROM simulation_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone() is None:
                raise RunAnalyticsNotFoundError("Simulation Run does not exist.")

            sessions = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT session_id, session_number, status, created_at,
                           started_at, ended_at, transcript_hash
                    FROM sessions
                    WHERE run_id = ?
                    ORDER BY session_number
                    """,
                    (run_id,),
                ).fetchall()
            ]
            events = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT event_id, session_id, sequence_number, event_type,
                           event_status, created_at
                    FROM events
                    WHERE run_id = ?
                    ORDER BY created_at, sequence_number, event_id
                    """,
                    (run_id,),
                ).fetchall()
            ]
            memories = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT memory_id, source_session_id, memory_type,
                           information_class, status, memory_version,
                           created_at
                    FROM memory_items
                    WHERE run_id = ?
                    ORDER BY created_at, memory_id
                    """,
                    (run_id,),
                ).fetchall()
            ]
            transitions = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT transition_id, session_id, event_id, variable_name,
                           validation_status, confidence, created_at
                    FROM character_state_transitions
                    WHERE run_id = ?
                    ORDER BY created_at, transition_id
                    """,
                    (run_id,),
                ).fetchall()
            ]
            plan_rows = connection.execute(
                """
                SELECT revision_id, revision_number, status, plan_json,
                       created_at
                FROM treatment_plan_revisions
                WHERE run_id = ?
                ORDER BY revision_number
                """,
                (run_id,),
            ).fetchall()
            plan_revisions = [
                {
                    "revision_id": row["revision_id"],
                    "revision_number": row["revision_number"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                }
                for row in plan_rows
            ]
            current_plan = None
            for row in plan_rows:
                if row["status"] != "active":
                    continue
                try:
                    plan_payload = json.loads(row["plan_json"])
                except json.JSONDecodeError:
                    raise RunAnalyticsIntegrityError(
                        "The active treatment plan contains invalid JSON."
                    ) from None
                current_plan = {
                    "revision_id": row["revision_id"],
                    "revision_number": row["revision_number"],
                    "goal_status_counts": self._plan_goal_counts(plan_payload),
                }
                break

        all_evaluations = self._evaluation_service.list_run_evaluations(
            run_id=run_id
        )
        evaluations = [
            {
                "evaluation_id": record["evaluation_id"],
                "evaluation_scope": record["evaluation_scope"],
                "session_id": record["session_id"],
                "rubric_id": record["rubric_id"],
                "rubric_version": record["rubric_version"],
                "rubric_version_id": record["rubric_version_id"],
                "rubric_content_hash": record["rubric_content_hash"],
                "status": record["status"],
                "stale": record["stale"],
                "created_at": record["created_at"],
            }
            for record in all_evaluations
        ]
        competency_trajectories = self._competency_trajectories(
            run_id=run_id,
            sessions=sessions,
            evaluations=all_evaluations,
        )
        timestamps = [
            record["created_at"]
            for records in (
                sessions,
                events,
                memories,
                transitions,
                plan_revisions,
                evaluations,
            )
            for record in records
            if isinstance(record.get("created_at"), str)
        ]
        return RunAnalyticsSnapshot(
            data_scope="simulation_run",
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            time_range_start=min(timestamps) if timestamps else None,
            time_range_end=max(timestamps) if timestamps else None,
            sessions=tuple(sessions),
            events=tuple(events),
            event_counts=self._counts(events, "event_status"),
            memories=tuple(memories),
            memory_counts=self._counts(memories, "status"),
            state_transitions=tuple(transitions),
            transition_counts=self._counts(transitions, "validation_status"),
            plan_revisions=tuple(plan_revisions),
            current_plan=current_plan,
            evaluations=tuple(evaluations),
            competency_trajectories=competency_trajectories,
            limitations=(
                "Experimental operational analytics; not a clinical outcome measure.",
                "Counts do not establish therapeutic effectiveness or competency.",
                "Competency observations are raw session-level rubric results grouped by exact rubric version; no trend score or average is calculated.",
                "Missing session observations mean no reportable score is available, not that the competency was absent.",
                "Evaluation staleness follows the evaluator's stored transcript and Run-scope validation.",
                "Transcript text and case details are intentionally excluded from this export.",
            ),
        )
