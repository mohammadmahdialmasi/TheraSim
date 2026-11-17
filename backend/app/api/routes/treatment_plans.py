"""Versioned treatment-plan and review endpoints scoped to one Run."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.api.routes.runs import RunService, get_run_service
from app.api.routes.auth import get_current_user
from app.services.local_auth import AuthenticatedUser
from app.services.treatment_plans import (
    PlanAdaptationGuidance,
    PlanEvidenceReference,
    PlanGoal,
    PlanIntervention,
    PlanObjective,
    TreatmentPlanConflictError,
    TreatmentPlanDefinition,
    TreatmentPlanEvidenceError,
    TreatmentPlanNotFoundError,
    TreatmentPlanRevision,
    TreatmentPlanService,
    TreatmentPlanValidationError,
)


router = APIRouter(
    prefix="/api/v1/simulation-runs/{run_id}/treatment-plan",
    tags=["Treatment Planning"],
)

class TreatmentPlanDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    initial_formulation: StrictStr = Field(min_length=1, max_length=8000)
    goals: list[PlanGoal] = Field(min_length=1, max_length=50)
    objectives: list[PlanObjective] = Field(default_factory=list, max_length=100)
    interventions: list[PlanIntervention] = Field(default_factory=list, max_length=100)
    outcome_measures: list[StrictStr] = Field(default_factory=list, max_length=50)
    review_after_session: int | None = Field(default=None, ge=1)

    def to_contract(self) -> TreatmentPlanDefinition:
        return TreatmentPlanDefinition.model_validate(self.model_dump())


class InitialTreatmentPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    definition: TreatmentPlanDefinitionRequest
    evidence: list[PlanEvidenceReference] = Field(default_factory=list, max_length=100)
    rationale: StrictStr = Field(default="Initial plan", min_length=1, max_length=4000)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Rationale must not be blank.")
        return value.strip()


class TreatmentPlanProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_revision_number: int = Field(ge=1)
    definition: TreatmentPlanDefinitionRequest
    evidence: list[PlanEvidenceReference] = Field(min_length=1, max_length=100)
    rationale: StrictStr = Field(min_length=1, max_length=4000)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Rationale must not be blank.")
        return value.strip()


class TreatmentPlanReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["accepted", "rejected"]
    rationale: StrictStr = Field(min_length=1, max_length=4000)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Rationale must not be blank.")
        return value.strip()


class TreatmentPlanRevisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    plan_id: str
    run_id: str
    revision_number: int
    based_on_revision_number: int | None
    modality: str
    protocol_id: str
    protocol_version: str
    definition: TreatmentPlanDefinition
    evidence: list[PlanEvidenceReference]
    rationale: str
    status: str
    created_at: str
    review: "TreatmentPlanReviewData | None"


class TreatmentPlanReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    revision_id: str
    run_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


class PlanAdaptationEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    session_id: str | None
    summary: str


class PlanAdaptationGuidanceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    recommendation: str
    rationale: str
    evidence: list[PlanAdaptationEvidenceData]


class TreatmentPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: TreatmentPlanRevisionData | None
    revisions: list[TreatmentPlanRevisionData]


class TreatmentPlanRevisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TreatmentPlanRevisionData


class PlanAdaptationGuidanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: PlanAdaptationGuidanceData


class TreatmentPlanReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TreatmentPlanRevisionData
    review: dict[str, str]


def get_treatment_plan_service(request: Request) -> TreatmentPlanService:
    service = getattr(request.app.state, "treatment_plan_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="treatment_plan_service_unavailable",
        )
    return service


def _revision_data(
    revision: TreatmentPlanRevision,
) -> TreatmentPlanRevisionData:
    return TreatmentPlanRevisionData(
        revision_id=revision.revision_id,
        plan_id=revision.plan_id,
        run_id=revision.run_id,
        revision_number=revision.revision_number,
        based_on_revision_number=revision.based_on_revision_number,
        modality=revision.modality,
        protocol_id=revision.protocol_id,
        protocol_version=revision.protocol_version,
        definition=revision.definition,
        evidence=list(revision.evidence),
        rationale=revision.rationale,
        status=revision.status,
        created_at=revision.created_at,
        review=(
            TreatmentPlanReviewData(
                review_id=revision.review.review_id,
                revision_id=revision.review.revision_id,
                run_id=revision.review.run_id,
                decision=revision.review.decision,
                reviewer_id=revision.review.reviewer_id,
                rationale=revision.review.rationale,
                reviewed_at=revision.review.reviewed_at,
            )
            if revision.review is not None
            else None
        ),
    )


def _adaptation_guidance_data(
    guidance: PlanAdaptationGuidance,
) -> PlanAdaptationGuidanceData:
    return PlanAdaptationGuidanceData(
        status=guidance.status,
        recommendation=guidance.recommendation,
        rationale=guidance.rationale,
        evidence=[
            PlanAdaptationEvidenceData(
                event_id=item.event_id,
                event_type=item.event_type,
                session_id=item.session_id,
                summary=item.summary,
            )
            for item in guidance.evidence
        ],
    )


def _raise_plan_error(error: Exception) -> None:
    if isinstance(error, TreatmentPlanNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="treatment_plan_not_found",
        ) from None
    if isinstance(error, TreatmentPlanConflictError):
        raise HTTPException(
            status_code=409,
            detail="treatment_plan_conflict",
        ) from None
    if isinstance(error, TreatmentPlanEvidenceError):
        raise HTTPException(
            status_code=422,
            detail="treatment_plan_evidence_invalid",
        ) from None
    if isinstance(error, TreatmentPlanValidationError):
        raise HTTPException(
            status_code=422,
            detail="treatment_plan_invalid",
        ) from None
    raise HTTPException(
        status_code=500,
        detail="treatment_plan_service_error",
    ) from None


def _ensure_run(run_id: str, run_service: RunService):
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation_run_not_found")
    return run


@router.get("", response_model=TreatmentPlanListResponse)
def get_treatment_plan(
    run_id: str,
    service: TreatmentPlanService = Depends(get_treatment_plan_service),
    run_service: RunService = Depends(get_run_service),
):
    """Return all immutable plan revisions and the active revision."""

    _ensure_run(run_id, run_service)
    revisions = service.list_revisions(run_id)
    current = next(
        (revision for revision in revisions if revision.status == "active"),
        None,
    )
    return TreatmentPlanListResponse(
        current=_revision_data(current) if current else None,
        revisions=[_revision_data(revision) for revision in revisions],
    )


@router.get(
    "/adaptation-guidance",
    response_model=PlanAdaptationGuidanceResponse,
)
def get_treatment_plan_adaptation_guidance(
    run_id: str,
    service: TreatmentPlanService = Depends(get_treatment_plan_service),
    run_service: RunService = Depends(get_run_service),
):
    """Assess only newly accepted evidence and recommend human review steps."""

    _ensure_run(run_id, run_service)
    try:
        guidance = service.get_adaptation_guidance(run_id)
    except (
        TreatmentPlanNotFoundError,
        TreatmentPlanConflictError,
        TreatmentPlanEvidenceError,
        TreatmentPlanValidationError,
    ) as exc:
        _raise_plan_error(exc)
    return PlanAdaptationGuidanceResponse(
        data=_adaptation_guidance_data(guidance)
    )


@router.post("", response_model=TreatmentPlanRevisionResponse, status_code=201)
def create_initial_treatment_plan(
    run_id: str,
    request: InitialTreatmentPlanRequest,
    service: TreatmentPlanService = Depends(get_treatment_plan_service),
    run_service: RunService = Depends(get_run_service),
):
    """Create the first explicit plan version for a simulation Run."""

    run = _ensure_run(run_id, run_service)
    created_at = _now_utc()
    try:
        revision = service.create_initial_plan(
            run,
            definition=request.definition.to_contract(),
            evidence=tuple(request.evidence),
            rationale=request.rationale,
            created_at=created_at,
        )
    except (
        TreatmentPlanNotFoundError,
        TreatmentPlanConflictError,
        TreatmentPlanEvidenceError,
        TreatmentPlanValidationError,
    ) as exc:
        _raise_plan_error(exc)
    return TreatmentPlanRevisionResponse(data=_revision_data(revision))


@router.post(
    "/revisions",
    response_model=TreatmentPlanRevisionResponse,
    status_code=201,
)
def propose_treatment_plan_revision(
    run_id: str,
    request: TreatmentPlanProposalRequest,
    service: TreatmentPlanService = Depends(get_treatment_plan_service),
    run_service: RunService = Depends(get_run_service),
):
    """Submit an evidence-linked plan proposal for explicit human review."""

    _ensure_run(run_id, run_service)
    try:
        revision = service.propose_revision(
            run_id,
            expected_revision_number=request.expected_revision_number,
            definition=request.definition.to_contract(),
            evidence=tuple(request.evidence),
            rationale=request.rationale,
            created_at=_now_utc(),
        )
    except (
        TreatmentPlanNotFoundError,
        TreatmentPlanConflictError,
        TreatmentPlanEvidenceError,
        TreatmentPlanValidationError,
    ) as exc:
        _raise_plan_error(exc)
    return TreatmentPlanRevisionResponse(data=_revision_data(revision))


@router.post(
    "/revisions/{revision_id}/review",
    response_model=TreatmentPlanReviewResponse,
)
def review_treatment_plan_revision(
    run_id: str,
    revision_id: str,
    request: TreatmentPlanReviewRequest,
    service: TreatmentPlanService = Depends(get_treatment_plan_service),
    run_service: RunService = Depends(get_run_service),
    reviewer: AuthenticatedUser = Depends(get_current_user),
):
    """Accept or reject a pending plan proposal with an immutable rationale."""

    _ensure_run(run_id, run_service)
    try:
        revision, review = service.review_revision(
            run_id,
            revision_id,
            decision=request.decision,
            reviewer_id=reviewer.user_id,
            rationale=request.rationale,
            reviewed_at=_now_utc(),
        )
    except (
        TreatmentPlanNotFoundError,
        TreatmentPlanConflictError,
        TreatmentPlanEvidenceError,
        TreatmentPlanValidationError,
    ) as exc:
        _raise_plan_error(exc)
    return TreatmentPlanReviewResponse(
        data=_revision_data(revision),
        review={
            "review_id": review.review_id,
            "revision_id": review.revision_id,
            "run_id": review.run_id,
            "decision": review.decision,
            "reviewer_id": review.reviewer_id,
            "rationale": review.rationale,
            "reviewed_at": review.reviewed_at,
        },
    )


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
