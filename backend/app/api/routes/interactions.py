"""HTTP endpoints for synthetic psychotherapy interactions."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.interactions import (
    InteractionAttemptOwnershipLostError,
    InteractionGenerationError,
    InteractionIdempotencyConflictError,
    InteractionPersistenceIntegrityError,
    InteractionRecord,
    InteractionRunNotActiveError,
    InteractionService,
    InteractionServiceError,
    InteractionSessionBusyError,
    InteractionSessionNotActiveError,
    InteractionSessionNotFoundError,
)


router = APIRouter(
    prefix="/api/v1/sessions",
    tags=["Interactions"],
)


class TherapistMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=100000)

    @field_validator("content")
    @classmethod
    def validate_non_whitespace_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message content cannot be blank.")
        return value


class InteractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["processing", "completed"]
    session_id: str
    request_id: str
    attempt_number: int
    therapist_message_id: str
    therapist_content: str
    patient_message_id: str | None = None
    patient_content: str | None = None


def get_interaction_service(request: Request) -> InteractionService:
    service = getattr(request.app.state, "interaction_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="interaction_service_unavailable",
        )

    return service


def _raise_interaction_http_error(exc: InteractionServiceError) -> None:
    if isinstance(exc, InteractionSessionNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="session_not_found",
        ) from None

    if isinstance(exc, InteractionSessionNotActiveError):
        raise HTTPException(
            status_code=409,
            detail="session_not_active",
        ) from None

    if isinstance(exc, InteractionRunNotActiveError):
        raise HTTPException(
            status_code=409,
            detail="run_not_active",
        ) from None

    if isinstance(exc, InteractionIdempotencyConflictError):
        raise HTTPException(
            status_code=409,
            detail="idempotency_conflict",
        ) from None

    if isinstance(exc, InteractionSessionBusyError):
        raise HTTPException(
            status_code=409,
            detail="session_has_unresolved_interaction",
        ) from None

    if isinstance(exc, InteractionAttemptOwnershipLostError):
        raise HTTPException(
            status_code=409,
            detail="interaction_attempt_ownership_lost",
        ) from None

    if isinstance(exc, InteractionGenerationError):
        if exc.error_code == "provider_unavailable":
            status_code = 503
        elif exc.error_code == "provider_timeout":
            status_code = 504
        elif exc.error_code in {
            "provider_error",
            "incomplete_model_response",
            "invalid_agent_output",
        }:
            status_code = 502
        else:
            status_code = 500

        raise HTTPException(
            status_code=status_code,
            detail=exc.error_code,
        ) from None

    if isinstance(exc, InteractionPersistenceIntegrityError):
        raise HTTPException(
            status_code=500,
            detail="interaction_persistence_integrity_error",
        ) from None

    raise HTTPException(
        status_code=500,
        detail="interaction_service_error",
    ) from None


@router.post(
    "/{session_id}/messages",
    response_model=InteractionResponse,
    status_code=200,
    responses={
        202: {"model": InteractionResponse, "description": "Interaction is processing."},
        404: {"description": "Session was not found."},
        409: {"description": "Interaction conflict or unresolved request."},
        422: {"description": "Invalid request payload or headers."},
        502: {"description": "Local model returned an invalid response."},
        503: {"description": "Interaction service or local provider is unavailable."},
        504: {"description": "Local model request timed out."},
    },
)
def create_session_message(
    session_id: str,
    body: TherapistMessageRequest,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=200,
        ),
    ],
    service: InteractionService = Depends(get_interaction_service),
):
    """Persist a therapist turn and generate one validated synthetic reply."""

    if not idempotency_key.strip():
        raise HTTPException(
            status_code=422,
            detail="invalid_idempotency_key",
        )

    try:
        result: InteractionRecord = service.handle_message(
            session_id=session_id,
            idempotency_key=idempotency_key,
            content=body.content,
        )
    except InteractionServiceError as exc:
        _raise_interaction_http_error(exc)

    response = InteractionResponse(
        status=result.status,
        session_id=result.session_id,
        request_id=result.request_id,
        attempt_number=result.attempt_number,
        therapist_message_id=result.therapist_message_id,
        therapist_content=result.therapist_content,
        patient_message_id=result.patient_message_id,
        patient_content=result.patient_content,
    )

    if response.status == "processing":
        return JSONResponse(
            status_code=202,
            content=response.model_dump(),
            headers={"Retry-After": "2"},
        )

    return response
