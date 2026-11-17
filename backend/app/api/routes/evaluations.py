"""Evaluation API endpoints for session and run-level rubrics."""

from typing import Literal, NoReturn
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.routes.auth import get_current_user
from app.services.evaluations import (
    EvaluationNotFoundError,
    EvaluationRunError,
    EvaluationRubricError,
    EvaluationGenerationError,
    EvaluationReviewUnavailableError,
    EvaluationService,
    EvaluationServiceError,
    EvaluationSessionError,
    EvaluationUnavailableError,
)
from app.services.local_auth import AuthenticatedUser

router = APIRouter(prefix="/api/v1", tags=["Evaluations"])


class EvaluationEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_item_id: str
    message_id: str
    session_id: str | None = None
    session_number: int | None = None
    source_role: str | None = None
    source_message_content: str | None = None
    evidence_role: str
    start_offset: int | None = None
    end_offset: int | None = None
    evidence_excerpt: str | None = None
    evidence_note: str | None = None


class EvaluationSessionScopeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    session_number: int
    transcript_sha256: str


class EvaluationItemData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_item_id: str
    evaluation_id: str
    competency_id: str
    rating_code: str
    justification: str | None = None
    alternative_response: str | None = None
    limitations: str | None = None
    uncertainty_notes: str | None = None
    confidence: str | None = None
    strengths: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    evidence: list[EvaluationEvidenceData] = Field(default_factory=list)


class EvaluationReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    evaluation_id: str
    review_number: int
    reviewer_user_id: str
    reviewer_name: str
    decision: Literal["accepted", "revision_requested"]
    feedback: str
    created_at: str


class EvaluationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "revision_requested"]
    feedback: str = Field(min_length=1, max_length=4000)

    @field_validator("feedback")
    @classmethod
    def feedback_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Review feedback cannot be blank.")
        return value.strip()


class EvaluationReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: EvaluationReviewData


class EvaluationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    run_id: str
    session_id: str | None = None
    evaluation_scope: str
    rubric_id: str
    rubric_version: str
    evaluation_revision: int = 1
    status: str
    created_at: str
    stale: bool = False
    overall_summary: str | None = None
    experimental: bool = True
    human_review_required: bool = True
    review_status: Literal[
        "pending",
        "accepted",
        "revision_requested",
    ] = "pending"
    reviews: list[EvaluationReviewData] = Field(default_factory=list)
    evaluator_model: str | None = None
    evaluator_prompt_version: str | None = None
    rubric_content_sha256: str | None = None
    session_scope: list[EvaluationSessionScopeData] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    items: list[EvaluationItemData] = Field(default_factory=list)


class EvaluationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: EvaluationData


class EvaluationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[EvaluationData]


def get_evaluation_service(request: Request) -> EvaluationService:
    service = getattr(request.app.state, "evaluation_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="evaluation_service_unavailable")
    return service


def _item_response(item: dict, evidence: list[dict]) -> EvaluationItemData:
    return EvaluationItemData(
        evaluation_item_id=item["evaluation_item_id"],
        evaluation_id=item["evaluation_id"],
        competency_id=item["competency_id"],
        rating_code=item["rating_code"],
        justification=item.get("justification"),
        alternative_response=item.get("alternative_response"),
        limitations=item.get("limitations"),
        uncertainty_notes=item.get("uncertainty_notes"),
        evidence=[
            EvaluationEvidenceData(
                evaluation_item_id=entry["evaluation_item_id"],
                message_id=entry["message_id"],
                session_id=entry.get("session_id"),
                session_number=entry.get("session_number"),
                source_role=entry.get("source_role"),
                source_message_content=entry.get("source_message_content"),
                evidence_role=entry["evidence_role"],
                start_offset=entry.get("start_offset"),
                end_offset=entry.get("end_offset"),
                evidence_excerpt=entry.get("evidence_excerpt"),
                evidence_note=entry.get("evidence_note"),
            )
            for entry in evidence
        ],
    )


def _evaluation_response(record: dict, service: EvaluationService) -> EvaluationData:
    if record.get("evaluator_model_run_id") is None:
        return EvaluationData(
            evaluation_id=record["evaluation_id"],
            run_id=record["run_id"],
            session_id=record.get("session_id"),
            evaluation_scope=record["evaluation_scope"],
            rubric_id=record.get("rubric_id", "ACT_RUBRIC_V0"),
            rubric_version=record.get("rubric_version", "0.2"),
            evaluation_revision=record.get("evaluation_revision", 1),
            status="experimental",
            created_at=record["created_at"],
            stale=record.get("stale", False),
            experimental=True,
            human_review_required=True,
            review_status="pending",
            reviews=[],
            limitations=[
                "Historical record has no evaluator model execution.",
                "Stored ratings and evidence are withheld.",
            ],
            overall_summary=(
                "This historical record has no Evaluator Agent execution. "
                "Its stored placeholder ratings and evidence are withheld."
            ),
            items=[],
        )

    metadata_value = record.get("report_metadata")
    metadata = (
        json.loads(metadata_value)
        if isinstance(metadata_value, str)
        else {}
    )
    if not isinstance(metadata, dict):
        raise ValueError("Stored evaluation report metadata is invalid.")
    competency_metadata = metadata.get("competencies", {})
    if not isinstance(competency_metadata, dict):
        raise ValueError("Stored competency report metadata is invalid.")

    items = service.list_items(evaluation_id=record["evaluation_id"])
    item_payload: list[EvaluationItemData] = []
    for item in items:
        evidence = service.list_evidence_for_item(
            evaluation_item_id=item["evaluation_item_id"]
        )
        item_data = _item_response(item, evidence)
        extra = competency_metadata.get(item["competency_id"], {})
        if not isinstance(extra, dict):
            raise ValueError("Stored competency metadata has an invalid shape.")
        item_payload.append(
            EvaluationItemData.model_validate({
                **item_data.model_dump(),
                "confidence": extra.get("confidence"),
                "strengths": extra.get("strengths", []),
                "missing_evidence": extra.get("missing_evidence", []),
            })
        )

    reviews = [
        EvaluationReviewData.model_validate(review)
        for review in service.list_reviews(
            evaluation_id=record["evaluation_id"]
        )
    ]
    latest_review = reviews[-1] if reviews else None
    return EvaluationData(
        evaluation_id=record["evaluation_id"],
        run_id=record["run_id"],
        session_id=record.get("session_id"),
        evaluation_scope=record["evaluation_scope"],
        rubric_id=record.get("rubric_id", "ACT_RUBRIC_V0"),
        rubric_version=record.get("rubric_version", "0.2"),
        evaluation_revision=record.get("evaluation_revision", 1),
        status=record["status"],
        created_at=record["created_at"],
        stale=record.get("stale", False),
        overall_summary=record.get("overall_summary"),
        experimental=metadata.get("experimental", True),
        human_review_required=(
            latest_review.decision != "accepted"
            if latest_review is not None
            else metadata.get("human_review_required", True)
        ),
        review_status=(
            latest_review.decision
            if latest_review is not None
            else "pending"
        ),
        reviews=reviews,
        evaluator_model=metadata.get("evaluator_model"),
        evaluator_prompt_version=metadata.get("evaluator_prompt_version"),
        rubric_content_sha256=metadata.get("rubric_content_sha256"),
        limitations=metadata.get("limitations", []),
        session_scope=metadata.get("longitudinal_session_scope", []),
        items=item_payload,
    )


def _raise_evaluation_http_error(exc: EvaluationServiceError) -> NoReturn:
    if isinstance(exc, EvaluationUnavailableError):
        raise HTTPException(
            status_code=503,
            detail="evaluator_unavailable_experimental",
        ) from None
    if isinstance(exc, EvaluationSessionError):
        raise HTTPException(status_code=409, detail="session_evaluation_unavailable") from None
    if isinstance(exc, EvaluationRunError):
        raise HTTPException(status_code=409, detail="run_evaluation_unavailable") from None
    if isinstance(exc, EvaluationGenerationError):
        raise HTTPException(
            status_code=502,
            detail="evaluation_generation_failed",
        ) from None
    if isinstance(exc, EvaluationNotFoundError):
        raise HTTPException(status_code=404, detail="evaluation_not_found") from None
    if isinstance(exc, EvaluationReviewUnavailableError):
        raise HTTPException(
            status_code=409,
            detail="evaluation_review_unavailable",
        ) from None
    if isinstance(exc, EvaluationRubricError):
        raise HTTPException(status_code=422, detail="unsupported_rubric") from None
    raise HTTPException(status_code=500, detail="evaluation_service_error") from None


@router.post(
    "/sessions/{session_id}/evaluations",
    response_model=EvaluationResponse,
    status_code=201,
    responses={
        503: {"description": "The experimental Evaluator Agent is unavailable."}
    },
)
def create_session_evaluation(
    session_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
    rubric_id: str = "ACT_RUBRIC_V0",
    rubric_version: str = "0.2",
) -> EvaluationResponse:
    try:
        record = service.generate_session_evaluation(
            session_id=session_id,
            rubric_id=rubric_id,
            rubric_version=rubric_version,
        )
    except EvaluationServiceError as exc:
        _raise_evaluation_http_error(exc)
    return EvaluationResponse(data=_evaluation_response(record, service))


@router.post(
    "/simulation-runs/{run_id}/evaluations",
    response_model=EvaluationResponse,
    status_code=201,
    responses={
        503: {"description": "The experimental Evaluator Agent is unavailable."}
    },
)
def create_run_evaluation(
    run_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
    rubric_id: str = "ACT_LONGITUDINAL_RUBRIC_V0",
    rubric_version: str = "0.2",
) -> EvaluationResponse:
    try:
        record = service.generate_run_evaluation(
            run_id=run_id,
            rubric_id=rubric_id,
            rubric_version=rubric_version,
        )
    except EvaluationServiceError as exc:
        _raise_evaluation_http_error(exc)
    return EvaluationResponse(data=_evaluation_response(record, service))


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=EvaluationResponse,
)
def get_evaluation(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationResponse:
    evaluation = service.get_evaluation(evaluation_id=evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="evaluation_not_found")
    return EvaluationResponse(data=_evaluation_response(evaluation, service))


@router.post(
    "/evaluations/{evaluation_id}/reviews",
    response_model=EvaluationReviewResponse,
    status_code=201,
)
def add_evaluation_review(
    evaluation_id: str,
    payload: EvaluationReviewRequest,
    reviewer: AuthenticatedUser = Depends(get_current_user),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReviewResponse:
    try:
        review = service.add_review(
            evaluation_id=evaluation_id,
            reviewer_user_id=reviewer.user_id,
            decision=payload.decision,
            feedback=payload.feedback,
        )
    except EvaluationServiceError as exc:
        _raise_evaluation_http_error(exc)
    return EvaluationReviewResponse(
        data=EvaluationReviewData.model_validate(review)
    )


@router.get(
    "/simulation-runs/{run_id}/evaluations",
    response_model=EvaluationListResponse,
)
def list_run_evaluations(
    run_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationListResponse:
    rows = service.list_run_evaluations(run_id=run_id)
    return EvaluationListResponse(
        data=[_evaluation_response(row, service) for row in rows]
    )


@router.get(
    "/sessions/{session_id}/evaluations",
    response_model=EvaluationListResponse,
)
def list_session_evaluations(
    session_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationListResponse:
    rows = service.list_session_evaluations(session_id=session_id)
    return EvaluationListResponse(
        data=[_evaluation_response(row, service) for row in rows]
    )
