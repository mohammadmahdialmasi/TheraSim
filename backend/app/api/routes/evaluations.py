"""Evaluation API endpoints for session and run-level rubrics."""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.evaluations import (
    EvaluationNotFoundError,
    EvaluationRunError,
    EvaluationRubricError,
    EvaluationService,
    EvaluationServiceError,
    EvaluationSessionError,
    EvaluationUnavailableError,
)

router = APIRouter(prefix="/api/v1", tags=["Evaluations"])


class EvaluationEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_item_id: str
    message_id: str
    evidence_role: str
    start_offset: int | None = None
    end_offset: int | None = None
    evidence_excerpt: str | None = None
    evidence_note: str | None = None


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
    evidence: list[EvaluationEvidenceData] = Field(default_factory=list)


class EvaluationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: str
    run_id: str
    session_id: str | None = None
    evaluation_scope: str
    rubric_id: str
    rubric_version: str
    status: str
    created_at: str
    overall_summary: str | None = None
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
            status="experimental",
            created_at=record["created_at"],
            overall_summary=(
                "This historical record has no Evaluator Agent execution. "
                "Its stored placeholder ratings and evidence are withheld."
            ),
            items=[],
        )

    items = service.list_items(evaluation_id=record["evaluation_id"])
    item_payload: list[EvaluationItemData] = []
    for item in items:
        evidence = service.list_evidence_for_item(
            evaluation_item_id=item["evaluation_item_id"]
        )
        item_payload.append(_item_response(item, evidence))

    return EvaluationData(
        evaluation_id=record["evaluation_id"],
        run_id=record["run_id"],
        session_id=record.get("session_id"),
        evaluation_scope=record["evaluation_scope"],
        rubric_id=record.get("rubric_id", "ACT_RUBRIC_V0"),
        rubric_version=record.get("rubric_version", "0.2"),
        status=record["status"],
        created_at=record["created_at"],
        overall_summary=record.get("overall_summary"),
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
    if isinstance(exc, EvaluationNotFoundError):
        raise HTTPException(status_code=404, detail="evaluation_not_found") from None
    if isinstance(exc, EvaluationRubricError):
        raise HTTPException(status_code=422, detail="unsupported_rubric") from None
    raise HTTPException(status_code=500, detail="evaluation_service_error") from None


@router.post(
    "/sessions/{session_id}/evaluations",
    response_model=None,
    status_code=503,
    responses={
        503: {"description": "The experimental Evaluator Agent is unavailable."}
    },
)
def create_session_evaluation(
    session_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
    rubric_id: str = "ACT_RUBRIC_V0",
    rubric_version: str = "0.2",
) -> NoReturn:
    try:
        service.generate_session_evaluation(
            session_id=session_id,
            rubric_id=rubric_id,
            rubric_version=rubric_version,
        )
    except EvaluationServiceError as exc:
        _raise_evaluation_http_error(exc)


@router.post(
    "/simulation-runs/{run_id}/evaluations",
    response_model=None,
    status_code=503,
    responses={
        503: {"description": "The experimental Evaluator Agent is unavailable."}
    },
)
def create_run_evaluation(
    run_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
    rubric_id: str = "ACT_LONGITUDINAL_RUBRIC_V0",
    rubric_version: str = "0.2",
) -> NoReturn:
    try:
        service.generate_run_evaluation(
            run_id=run_id,
            rubric_id=rubric_id,
            rubric_version=rubric_version,
        )
    except EvaluationServiceError as exc:
        _raise_evaluation_http_error(exc)


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
