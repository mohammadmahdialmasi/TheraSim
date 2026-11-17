"""Versioned treatment plans with evidence-checked, review-gated revisions."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from app.persistence.database import DatabaseManager
from app.services.runs import SimulationRunRecord


EvidenceKind = Literal["event", "state_transition", "session", "evaluation"]


class TreatmentPlanError(RuntimeError):
    """Base error for treatment-plan operations."""


class TreatmentPlanNotFoundError(TreatmentPlanError):
    """No treatment plan or revision exists in the requested Run."""


class TreatmentPlanConflictError(TreatmentPlanError):
    """The proposed revision is stale or already reviewed."""


class TreatmentPlanEvidenceError(TreatmentPlanError):
    """A proposal cites evidence outside the Run or not approved for use."""


class TreatmentPlanValidationError(TreatmentPlanError):
    """The plan definition is malformed."""


class PlanEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: EvidenceKind
    source_id: StrictStr = Field(min_length=1, max_length=200)


class PlanGoal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    goal_id: StrictStr = Field(min_length=1, max_length=100)
    description: StrictStr = Field(min_length=1, max_length=2000)
    relevant_processes: list[StrictStr] = Field(default_factory=list, max_length=20)
    status: Literal["active", "paused", "achieved"] = "active"
    progress_notes: StrictStr = Field(default="", max_length=2000)


class PlanObjective(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    objective_id: StrictStr = Field(min_length=1, max_length=100)
    goal_id: StrictStr = Field(min_length=1, max_length=100)
    description: StrictStr = Field(min_length=1, max_length=2000)
    status: Literal["active", "paused", "achieved"] = "active"
    progress_indicator: StrictStr = Field(min_length=1, max_length=1000)


class PlanIntervention(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intervention_id: StrictStr = Field(min_length=1, max_length=100)
    description: StrictStr = Field(min_length=1, max_length=2000)
    objective_ids: list[StrictStr] = Field(default_factory=list, max_length=50)
    status: Literal["proposed", "active", "paused", "completed"] = "proposed"


class TreatmentPlanDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    initial_formulation: StrictStr = Field(min_length=1, max_length=8000)
    goals: list[PlanGoal] = Field(min_length=1, max_length=50)
    objectives: list[PlanObjective] = Field(default_factory=list, max_length=100)
    interventions: list[PlanIntervention] = Field(default_factory=list, max_length=100)
    outcome_measures: list[StrictStr] = Field(default_factory=list, max_length=50)
    review_after_session: int | None = Field(default=None, ge=1)

    @classmethod
    def parse_definition(
        cls,
        value: TreatmentPlanDefinition | dict[str, object],
    ) -> TreatmentPlanDefinition:
        try:
            if isinstance(value, cls):
                definition = value
            else:
                definition = cls.model_validate(value)
        except ValidationError as exc:
            raise TreatmentPlanValidationError(
                "Treatment-plan definition failed validation."
            ) from exc

        goal_ids = [goal.goal_id for goal in definition.goals]
        objective_ids = [objective.objective_id for objective in definition.objectives]
        intervention_ids = [
            item.intervention_id for item in definition.interventions
        ]
        if (
            len(goal_ids) != len(set(goal_ids))
            or len(objective_ids) != len(set(objective_ids))
            or len(intervention_ids) != len(set(intervention_ids))
        ):
            raise TreatmentPlanValidationError(
                "Treatment-plan identifiers must be unique."
            )
        text_values = [
            definition.initial_formulation,
            *(goal.goal_id for goal in definition.goals),
            *(goal.description for goal in definition.goals),
            *(objective.objective_id for objective in definition.objectives),
            *(objective.goal_id for objective in definition.objectives),
            *(objective.description for objective in definition.objectives),
            *(objective.progress_indicator for objective in definition.objectives),
            *(item.intervention_id for item in definition.interventions),
            *(item.description for item in definition.interventions),
            *definition.outcome_measures,
        ]
        if any(not item.strip() for item in text_values):
            raise TreatmentPlanValidationError(
                "Treatment-plan text fields must not be blank."
            )
        if any(objective.goal_id not in set(goal_ids) for objective in definition.objectives):
            raise TreatmentPlanValidationError(
                "Every objective must reference a goal in this plan."
            )
        if any(
            objective_id not in set(objective_ids)
            for intervention in definition.interventions
            for objective_id in intervention.objective_ids
        ):
            raise TreatmentPlanValidationError(
                "Interventions may reference only plan objectives."
            )
        return definition


@dataclass(frozen=True, slots=True)
class TreatmentPlanRevision:
    revision_id: str
    plan_id: str
    run_id: str
    revision_number: int
    based_on_revision_number: int | None
    modality: str
    protocol_id: str
    protocol_version: str
    definition: TreatmentPlanDefinition
    evidence: tuple[PlanEvidenceReference, ...]
    rationale: str
    status: str
    created_at: str
    review: TreatmentPlanReview | None = None


@dataclass(frozen=True, slots=True)
class TreatmentPlanReview:
    review_id: str
    revision_id: str
    run_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


@dataclass(frozen=True, slots=True)
class PlanAdaptationEvidence:
    event_id: str
    event_type: str
    session_id: str | None
    summary: str


@dataclass(frozen=True, slots=True)
class PlanAdaptationGuidance:
    status: str
    recommendation: str
    rationale: str
    evidence: tuple[PlanAdaptationEvidence, ...]


class TreatmentPlanService:
    """Creates plans and requires explicit review before revisions become active."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        self._database_manager = database_manager

    @staticmethod
    def _require_text(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be non-empty text.")
        return value.strip()

    @staticmethod
    def _from_row(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> TreatmentPlanRevision:
        try:
            payload = json.loads(row["plan_json"])
            definition = TreatmentPlanDefinition.parse_definition(
                payload["definition"]
            )
            evidence = tuple(
                PlanEvidenceReference.model_validate(item)
                for item in payload["evidence"]
            )
            rationale = payload["rationale"]
            if not isinstance(rationale, str):
                raise ValueError
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, ValidationError):
            raise TreatmentPlanValidationError(
                "Persisted treatment-plan revision is malformed."
            ) from None
        review_row = connection.execute(
            "SELECT * FROM treatment_plan_reviews WHERE revision_id = ?",
            (row["revision_id"],),
        ).fetchone()
        review = (
            TreatmentPlanReview(
                review_id=review_row["review_id"],
                revision_id=review_row["revision_id"],
                run_id=review_row["run_id"],
                decision=review_row["decision"],
                reviewer_id=review_row["reviewer_id"],
                rationale=review_row["rationale"],
                reviewed_at=review_row["reviewed_at"],
            )
            if review_row is not None
            else None
        )
        return TreatmentPlanRevision(
            revision_id=row["revision_id"],
            plan_id=row["plan_id"],
            run_id=row["run_id"],
            revision_number=row["revision_number"],
            based_on_revision_number=row["based_on_revision_number"],
            modality=row["modality"],
            protocol_id=row["protocol_id"],
            protocol_version=row["protocol_version"],
            definition=definition,
            evidence=evidence,
            rationale=rationale,
            status=row["status"],
            created_at=row["created_at"],
            review=review,
        )

    @staticmethod
    def _validate_references(
        connection: sqlite3.Connection,
        run_id: str,
        references: tuple[PlanEvidenceReference, ...],
    ) -> None:
        for reference in references:
            table, field = {
                "event": ("events", "event_id"),
                "state_transition": (
                    "character_state_transitions",
                    "transition_id",
                ),
                "session": ("sessions", "session_id"),
                "evaluation": ("evaluations", "evaluation_id"),
            }[reference.kind]
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {field} = ?",
                (reference.source_id,),
            ).fetchone()
            if row is None or row["run_id"] != run_id:
                raise TreatmentPlanEvidenceError(
                    "Treatment-plan evidence must belong to the same Run."
                )
            if reference.kind == "event" and row["event_status"] != "accepted":
                raise TreatmentPlanEvidenceError(
                    "Only accepted events can support a plan revision."
                )
            if (
                reference.kind == "state_transition"
                and row["validation_status"] != "accepted"
            ):
                raise TreatmentPlanEvidenceError(
                    "Only accepted state transitions can support a plan revision."
                )
            if reference.kind == "session" and row["status"] != "completed":
                raise TreatmentPlanEvidenceError(
                    "Only completed sessions can support a plan revision."
                )

    @staticmethod
    def _serialize(
        definition: TreatmentPlanDefinition,
        evidence: tuple[PlanEvidenceReference, ...],
        rationale: str,
    ) -> str:
        return json.dumps(
            {
                "definition": definition.model_dump(mode="json"),
                "evidence": [item.model_dump(mode="json") for item in evidence],
                "rationale": rationale,
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def get_current(self, run_id: str) -> TreatmentPlanRevision | None:
        self._require_text(run_id, "run_id")
        with self._database_manager.connection("operational") as connection:
            row = connection.execute(
                """
                SELECT * FROM treatment_plan_revisions
                WHERE run_id = ? AND status = 'active'
                """,
                (run_id,),
            ).fetchone()
            return self._from_row(connection, row) if row is not None else None

    def list_revisions(self, run_id: str) -> list[TreatmentPlanRevision]:
        self._require_text(run_id, "run_id")
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT * FROM treatment_plan_revisions
                WHERE run_id = ?
                ORDER BY revision_number
                """,
                (run_id,),
            ).fetchall()
            return [self._from_row(connection, row) for row in rows]

    def get_adaptation_guidance(
        self,
        run_id: str,
    ) -> PlanAdaptationGuidance:
        run_id = self._require_text(run_id, "run_id")
        with self._database_manager.connection("operational") as connection:
            active = connection.execute(
                """
                SELECT * FROM treatment_plan_revisions
                WHERE run_id = ? AND status = 'active'
                """,
                (run_id,),
            ).fetchone()
            if active is None:
                return PlanAdaptationGuidance(
                    status="no_plan",
                    recommendation="create_initial_plan",
                    rationale="Create an initial plan before considering adaptation.",
                    evidence=(),
                )

            current = self._from_row(connection, active)
            cited_event_ids = {
                item.source_id
                for item in current.evidence
                if item.kind == "event"
            }
            rows = connection.execute(
                """
                SELECT event_id, session_id, event_type, payload
                FROM events
                WHERE run_id = ?
                  AND event_status = 'accepted'
                  AND created_at > ?
                ORDER BY created_at, sequence_number, event_id
                """,
                (run_id, active["created_at"]),
            ).fetchall()
            events: list[PlanAdaptationEvidence] = []
            for row in rows:
                if row["event_id"] in cited_event_ids:
                    continue
                try:
                    payload = json.loads(row["payload"])
                except json.JSONDecodeError:
                    raise TreatmentPlanValidationError(
                        "An accepted event contains malformed persisted data."
                    ) from None
                if not isinstance(payload, dict):
                    raise TreatmentPlanValidationError(
                        "An accepted event payload must be an object."
                    )
                summary = payload.get("summary")
                if not isinstance(summary, str) or not summary.strip():
                    summary = row["event_type"].replace("_", " ")
                events.append(
                    PlanAdaptationEvidence(
                        event_id=row["event_id"],
                        event_type=row["event_type"],
                        session_id=row["session_id"],
                        summary=summary.strip(),
                    )
                )

            if events:
                event_types = {item.event_type for item in events}
                if "contradiction" in event_types:
                    recommendation = "review_formulation"
                    rationale = (
                        "Newly accepted contradiction evidence warrants human "
                        "review of the formulation; it does not establish which "
                        "account is correct."
                    )
                elif event_types & {
                    "setback",
                    "avoidance_episode",
                    "value_inconsistent_action",
                    "interpersonal_conflict",
                }:
                    recommendation = "review_objectives_and_interventions"
                    rationale = (
                        "Newly accepted difficulty or setback evidence is "
                        "available. Review objective fit and intervention "
                        "readiness; no plan change is applied automatically."
                    )
                elif event_types & {
                    "progress_indicator",
                    "value_consistent_action",
                    "defusion_experience",
                    "coping_change",
                }:
                    recommendation = "review_progress_and_continue"
                    rationale = (
                        "Newly accepted progress-related evidence is available. "
                        "Review goal progress and whether the current plan remains "
                        "appropriate; no outcome score is inferred."
                    )
                else:
                    recommendation = "human_review"
                    rationale = (
                        "Newly accepted evidence is available, but this service "
                        "does not infer a treatment change for its event type."
                    )
                return PlanAdaptationGuidance(
                    status="actionable",
                    recommendation=recommendation,
                    rationale=rationale,
                    evidence=tuple(events),
                )

            completed_sessions = connection.execute(
                """
                SELECT COUNT(*)
                FROM sessions
                WHERE run_id = ?
                  AND status = 'completed'
                  AND ended_at > ?
                """,
                (run_id, active["created_at"]),
            ).fetchone()[0]
            if completed_sessions:
                return PlanAdaptationGuidance(
                    status="insufficient_evidence",
                    recommendation="human_review",
                    rationale=(
                        "Completed sessions exist after this plan revision, but "
                        "no newly accepted event evidence is available. Do not "
                        "infer progress or setbacks from missing data."
                    ),
                    evidence=(),
                )
            return PlanAdaptationGuidance(
                status="no_new_evidence",
                recommendation="continue_current_plan",
                rationale=(
                    "No new accepted Run evidence is available since the active "
                    "plan revision. The current plan remains unchanged."
                ),
                evidence=(),
            )

    def create_initial_plan(
        self,
        run: SimulationRunRecord,
        *,
        definition: TreatmentPlanDefinition,
        evidence: tuple[PlanEvidenceReference, ...] = (),
        rationale: str = "Initial plan",
        created_at: str,
    ) -> TreatmentPlanRevision:
        if not isinstance(run, SimulationRunRecord):
            raise TypeError("run must be a SimulationRunRecord.")
        parsed_definition = TreatmentPlanDefinition.parse_definition(definition)
        rationale = self._require_text(rationale, "rationale")
        created_at = self._require_text(created_at, "created_at")
        if len({(item.kind, item.source_id) for item in evidence}) != len(evidence):
            raise TreatmentPlanValidationError(
                "Treatment-plan evidence references must be unique."
            )
        revision_id = f"plan-revision-{uuid.uuid4().hex}"
        plan_id = f"treatment-plan-{uuid.uuid4().hex}"
        payload = self._serialize(parsed_definition, evidence, rationale)
        with self._database_manager.transaction("operational") as connection:
            self._validate_references(connection, run.run_id, evidence)
            if connection.execute(
                "SELECT 1 FROM simulation_runs WHERE run_id = ?",
                (run.run_id,),
            ).fetchone() is None:
                raise TreatmentPlanNotFoundError("Simulation Run does not exist.")
            if connection.execute(
                "SELECT 1 FROM treatment_plan_revisions WHERE run_id = ?",
                (run.run_id,),
            ).fetchone() is not None:
                raise TreatmentPlanConflictError(
                    "An initial treatment plan already exists."
                )
            connection.execute(
                """
                INSERT INTO treatment_plan_revisions (
                    revision_id, plan_id, run_id, revision_number,
                    based_on_revision_number, modality, protocol_id,
                    protocol_version, plan_json, status, created_at
                )
                VALUES (?, ?, ?, 1, NULL, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    revision_id,
                    plan_id,
                    run.run_id,
                    run.modality,
                    run.protocol_id,
                    run.protocol_version,
                    payload,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM treatment_plan_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
            return self._from_row(connection, row)

    def propose_revision(
        self,
        run_id: str,
        *,
        expected_revision_number: int,
        definition: TreatmentPlanDefinition,
        evidence: tuple[PlanEvidenceReference, ...],
        rationale: str,
        created_at: str,
    ) -> TreatmentPlanRevision:
        run_id = self._require_text(run_id, "run_id")
        rationale = self._require_text(rationale, "rationale")
        created_at = self._require_text(created_at, "created_at")
        if (
            isinstance(expected_revision_number, bool)
            or not isinstance(expected_revision_number, int)
            or expected_revision_number < 1
        ):
            raise ValueError("expected_revision_number must be positive.")
        parsed_definition = TreatmentPlanDefinition.parse_definition(definition)
        if not evidence:
            raise TreatmentPlanEvidenceError(
                "Plan revisions require at least one supporting reference."
            )
        if len({(item.kind, item.source_id) for item in evidence}) != len(evidence):
            raise TreatmentPlanValidationError(
                "Treatment-plan evidence references must be unique."
            )

        with self._database_manager.transaction("operational") as connection:
            active = connection.execute(
                """
                SELECT * FROM treatment_plan_revisions
                WHERE run_id = ? AND status = 'active'
                """,
                (run_id,),
            ).fetchone()
            if active is None:
                raise TreatmentPlanNotFoundError(
                    "The Run has no active treatment plan."
                )
            if active["revision_number"] != expected_revision_number:
                raise TreatmentPlanConflictError(
                    "The proposed revision is based on a stale plan."
                )
            self._validate_references(connection, run_id, evidence)
            pending_exists = connection.execute(
                """
                SELECT 1 FROM treatment_plan_revisions
                WHERE run_id = ? AND status = 'requires_review'
                """,
                (run_id,),
            ).fetchone()
            if pending_exists is not None:
                raise TreatmentPlanConflictError(
                    "A treatment-plan revision is already awaiting review."
                )
            revision_id = f"plan-revision-{uuid.uuid4().hex}"
            latest_revision_number = connection.execute(
                """
                SELECT COALESCE(MAX(revision_number), 0)
                FROM treatment_plan_revisions
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()[0]
            revision_number = latest_revision_number + 1
            payload = self._serialize(parsed_definition, evidence, rationale)
            connection.execute(
                """
                INSERT INTO treatment_plan_revisions (
                    revision_id, plan_id, run_id, revision_number,
                    based_on_revision_number, modality, protocol_id,
                    protocol_version, plan_json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'requires_review', ?)
                """,
                (
                    revision_id,
                    active["plan_id"],
                    run_id,
                    revision_number,
                    expected_revision_number,
                    active["modality"],
                    active["protocol_id"],
                    active["protocol_version"],
                    payload,
                    created_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM treatment_plan_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
            return self._from_row(connection, row)

    def review_revision(
        self,
        run_id: str,
        revision_id: str,
        *,
        decision: Literal["accepted", "rejected"],
        reviewer_id: str,
        rationale: str,
        reviewed_at: str,
    ) -> tuple[TreatmentPlanRevision, TreatmentPlanReview]:
        run_id = self._require_text(run_id, "run_id")
        revision_id = self._require_text(revision_id, "revision_id")
        reviewer_id = self._require_text(reviewer_id, "reviewer_id")
        rationale = self._require_text(rationale, "rationale")
        reviewed_at = self._require_text(reviewed_at, "reviewed_at")
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected.")
        with self._database_manager.transaction("operational") as connection:
            revision = connection.execute(
                """
                SELECT * FROM treatment_plan_revisions
                WHERE revision_id = ? AND run_id = ?
                """,
                (revision_id, run_id),
            ).fetchone()
            if revision is None:
                raise TreatmentPlanNotFoundError(
                    "Treatment-plan revision does not exist."
                )
            existing = connection.execute(
                "SELECT * FROM treatment_plan_reviews WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["run_id"] == run_id
                    and existing["decision"] == decision
                    and existing["reviewer_id"] == reviewer_id
                    and existing["rationale"] == rationale
                ):
                    return (
                        self._from_row(connection, revision),
                        TreatmentPlanReview(
                            review_id=existing["review_id"],
                            revision_id=existing["revision_id"],
                            run_id=existing["run_id"],
                            decision=existing["decision"],
                            reviewer_id=existing["reviewer_id"],
                            rationale=existing["rationale"],
                            reviewed_at=existing["reviewed_at"],
                        ),
                    )
                raise TreatmentPlanConflictError(
                    "Treatment-plan revision already has a different decision."
                )
            if revision["status"] != "requires_review":
                raise TreatmentPlanConflictError(
                    "Only a pending plan revision can be reviewed."
                )

            if decision == "accepted":
                active = connection.execute(
                    """
                    SELECT * FROM treatment_plan_revisions
                    WHERE run_id = ? AND status = 'active'
                    """,
                    (run_id,),
                ).fetchone()
                if (
                    active is None
                    or active["plan_id"] != revision["plan_id"]
                    or revision["based_on_revision_number"]
                    != active["revision_number"]
                ):
                    raise TreatmentPlanConflictError(
                        "The active treatment plan changed after proposal."
                    )

            review_id = f"plan-review-{uuid.uuid4().hex}"
            connection.execute(
                """
                INSERT INTO treatment_plan_reviews (
                    review_id, revision_id, run_id, decision, reviewer_id,
                    rationale, reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    revision_id,
                    run_id,
                    decision,
                    reviewer_id,
                    rationale,
                    reviewed_at,
                ),
            )
            if decision == "accepted":
                connection.execute(
                    """
                    UPDATE treatment_plan_revisions
                    SET status = 'superseded'
                    WHERE run_id = ? AND status = 'active'
                    """,
                    (run_id,),
                )
                status = "active"
            else:
                status = "rejected"
            connection.execute(
                """
                UPDATE treatment_plan_revisions
                SET status = ?
                WHERE revision_id = ? AND run_id = ?
                """,
                (status, revision_id, run_id),
            )
            updated = connection.execute(
                "SELECT * FROM treatment_plan_revisions WHERE revision_id = ?",
                (revision_id,),
            ).fetchone()
            return (
                self._from_row(connection, updated),
                TreatmentPlanReview(
                    review_id=review_id,
                    revision_id=revision_id,
                    run_id=run_id,
                    decision=decision,
                    reviewer_id=reviewer_id,
                    rationale=rationale,
                    reviewed_at=reviewed_at,
                ),
            )
