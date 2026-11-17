"""Run-scoped access to extracted behavioral events and review decisions."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.routes.runs import RunService, get_run_service
from app.api.routes.auth import get_current_user
from app.services.event_reviews import (
    EventRecord,
    EventReviewConflictError,
    EventReviewNotFoundError,
    EventReviewRecord,
    EventReviewService,
)
from app.services.local_auth import AuthenticatedUser


router = APIRouter(
    prefix="/api/v1/simulation-runs/{run_id}/events",
    tags=["Behavioral Events"],
)

class EventEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    role: str
    excerpt: str | None
    annotation: str | None


class EventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: str
    session_id: str | None
    sequence_number: int
    event_type: str
    actor: str
    payload: dict[str, object]
    extraction_method: str
    extractor_version: str | None
    event_status: str
    created_at: str
    validated_at: str | None
    evidence: list[EventEvidenceData]


class EventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[EventData]


class EventReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["accepted", "rejected"]
    rationale: str = Field(min_length=1, max_length=4000)

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Rationale must not be blank.")
        return value.strip()


class EventReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    event_id: str
    run_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


class EventReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: EventData
    review: EventReviewData


def get_event_review_service(request: Request) -> EventReviewService:
    service = getattr(request.app.state, "event_review_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="event_review_service_unavailable",
        )
    return service


def _ensure_run_exists(run_id: str, service: RunService) -> None:
    if service.get_run(run_id) is None:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        )


def _event_data(event: EventRecord) -> EventData:
    return EventData(
        event_id=event.event_id,
        run_id=event.run_id,
        session_id=event.session_id,
        sequence_number=event.sequence_number,
        event_type=event.event_type,
        actor=event.actor,
        payload=event.payload,
        extraction_method=event.extraction_method,
        extractor_version=event.extractor_version,
        event_status=event.event_status,
        created_at=event.created_at,
        validated_at=event.validated_at,
        evidence=[
            EventEvidenceData(
                message_id=evidence.message_id,
                role=evidence.role,
                excerpt=evidence.excerpt,
                annotation=evidence.annotation,
            )
            for evidence in event.evidence
        ],
    )


@router.get("", response_model=EventListResponse)
def list_events(
    run_id: str,
    status: Literal[
        "candidate",
        "accepted",
        "rejected",
        "requires_review",
    ]
    | None = Query(default=None),
    service: EventReviewService = Depends(get_event_review_service),
    run_service: RunService = Depends(get_run_service),
):
    """List events with their source excerpts for one simulation Run."""

    _ensure_run_exists(run_id, run_service)
    return EventListResponse(
        data=[
            _event_data(event)
            for event in service.list_events(run_id, status=status)
        ]
    )


@router.post(
    "/{event_id}/review",
    response_model=EventReviewResponse,
)
def review_event(
    run_id: str,
    event_id: str,
    request: EventReviewRequest,
    service: EventReviewService = Depends(get_event_review_service),
    run_service: RunService = Depends(get_run_service),
    reviewer: AuthenticatedUser = Depends(get_current_user),
):
    """Accept or reject one event proposal with an immutable rationale."""

    _ensure_run_exists(run_id, run_service)
    reviewed_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    try:
        event, review = service.review_event(
            run_id=run_id,
            event_id=event_id,
            decision=request.decision,
            reviewer_id=reviewer.user_id,
            rationale=request.rationale,
            reviewed_at=reviewed_at,
        )
    except EventReviewNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="event_not_found",
        ) from None
    except EventReviewConflictError:
        raise HTTPException(
            status_code=409,
            detail="event_review_conflict",
        ) from None
    return EventReviewResponse(
        data=_event_data(event),
        review=EventReviewData(
            review_id=review.review_id,
            event_id=review.event_id,
            run_id=review.run_id,
            decision=review.decision,
            reviewer_id=review.reviewer_id,
            rationale=review.rationale,
            reviewed_at=review.reviewed_at,
        ),
    )
