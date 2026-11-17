"""Public read-only interaction request status endpoint."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.services.interaction_status import (
    InteractionRequestStatusRecord,
    InteractionRequestStatusService,
)


router = APIRouter(
    prefix="/api/v1/interaction-requests",
    tags=["Interaction Requests"],
)


class InteractionRequestStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    session_id: str
    processing_status: Literal["in_progress", "completed", "failed"]
    therapist_message_id: str | None
    patient_message_id: str | None
    error_code: str | None
    created_at: str
    completed_at: str | None


class InteractionRequestStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: InteractionRequestStatusData


def get_interaction_request_status_service(
    request: Request,
) -> InteractionRequestStatusService:
    service = getattr(
        request.app.state,
        "interaction_request_status_service",
        None,
    )

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="interaction_status_service_unavailable",
        )

    return service


@router.get(
    "/{request_id}",
    response_model=InteractionRequestStatusResponse,
    responses={
        404: {"description": "Interaction request was not found."},
        503: {"description": "Interaction status service is unavailable."},
    },
)
def get_interaction_request_status(
    request_id: str,
    service: InteractionRequestStatusService = Depends(
        get_interaction_request_status_service
    ),
):
    """Retrieve operational status without exposing internal execution data."""

    record: InteractionRequestStatusRecord | None = (
        service.get_request_status(request_id)
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="interaction_request_not_found",
        )

    return InteractionRequestStatusResponse(
        data=InteractionRequestStatusData(
            request_id=record.request_id,
            session_id=record.session_id,
            processing_status=record.processing_status,
            therapist_message_id=record.therapist_message_id,
            patient_message_id=record.patient_message_id,
            error_code=record.error_code,
            created_at=record.created_at,
            completed_at=record.completed_at,
        )
    )
