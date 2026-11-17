"""Session lifecycle and therapist-visible transcript API."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.services.runs import RunService
from app.services.sessions import (
    SessionHasUnresolvedInteractionsError,
    SessionInvalidCompletionReasonError,
    SessionMessageRecord,
    SessionNotFoundError,
    SessionOrderViolationError,
    SessionRecord,
    SessionRunNotActiveError,
    SessionRunNotFoundError,
    SessionService,
    SessionServiceError,
    SessionTransitionError,
    SessionConflictError,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Sessions"],
)


class CreateSessionRequest(BaseModel):
    """Session numbering and timing are controlled by the backend."""

    model_config = ConfigDict(extra="forbid")


class CompleteSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completion_reason: Literal[
        "normal",
        "trainee_ended",
        "system_interrupted",
    ] = "normal"


class SessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    run_id: str
    session_number: int
    status: str
    started_at: str | None
    ended_at: str | None
    transcript_version: int


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SessionData


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[SessionData]


class MessageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    sequence_number: int
    role: str
    content: str
    created_at: str


class PaginationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    offset: int
    total: int


class MessageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[MessageData]
    pagination: PaginationData


class SessionCompletionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: Literal["completed"]
    transcript_version: int
    ended_at: str | None


class SessionCompletionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SessionCompletionData


def get_session_service(request: Request) -> SessionService:
    service = getattr(request.app.state, "session_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="session_service_unavailable",
        )

    return service


def get_run_service(request: Request) -> RunService:
    service = getattr(request.app.state, "run_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="run_service_unavailable",
        )

    return service


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _session_data(session: SessionRecord) -> SessionData:
    return SessionData(
        session_id=session.session_id,
        run_id=session.run_id,
        session_number=session.session_number,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        transcript_version=session.transcript_version,
    )


def _raise_session_http_error(exc: SessionServiceError) -> None:
    if isinstance(exc, SessionNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="session_not_found",
        ) from None

    if isinstance(exc, SessionRunNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        ) from None

    if isinstance(exc, SessionInvalidCompletionReasonError):
        raise HTTPException(
            status_code=422,
            detail="invalid_completion_reason",
        ) from None

    if isinstance(exc, SessionHasUnresolvedInteractionsError):
        raise HTTPException(
            status_code=409,
            detail="session_has_unresolved_interactions",
        ) from None

    if isinstance(exc, SessionRunNotActiveError):
        raise HTTPException(
            status_code=409,
            detail="run_not_active",
        ) from None

    if isinstance(exc, SessionOrderViolationError):
        raise HTTPException(
            status_code=409,
            detail="session_order_violation",
        ) from None

    if isinstance(exc, SessionTransitionError):
        raise HTTPException(
            status_code=409,
            detail="invalid_session_state_transition",
        ) from None

    if isinstance(exc, SessionConflictError):
        raise HTTPException(
            status_code=409,
            detail="session_conflict",
        ) from None

    raise HTTPException(
        status_code=500,
        detail="session_service_error",
    ) from None


@router.post(
    "/simulation-runs/{run_id}/sessions",
    response_model=SessionResponse,
    status_code=201,
    responses={
        404: {"description": "Simulation run was not found."},
        409: {"description": "Run state or sequential session conflict."},
        422: {"description": "Invalid request body."},
    },
)
def create_session(
    run_id: str,
    body: CreateSessionRequest,
    service: SessionService = Depends(get_session_service),
):
    """Create the next sequential active session."""

    try:
        session = service.create_next_session(
            session_id=str(uuid4()),
            run_id=run_id,
            created_at=_now_utc(),
        )
    except SessionServiceError as exc:
        _raise_session_http_error(exc)

    return SessionResponse(data=_session_data(session))


@router.get(
    "/simulation-runs/{run_id}/sessions",
    response_model=SessionListResponse,
)
def list_run_sessions(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """List sessions belonging to an existing simulation run."""

    if run_service.get_run(run_id) is None:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        )

    sessions = session_service.list_sessions(run_id)

    return SessionListResponse(
        data=[_session_data(item) for item in sessions]
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
)
def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """Retrieve authorized session metadata."""

    session = service.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="session_not_found",
        )

    return SessionResponse(data=_session_data(session))


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
)
def list_session_messages(
    session_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: SessionService = Depends(get_session_service),
):
    """Retrieve a paginated therapist-visible transcript."""

    try:
        messages, total = service.list_messages(
            session_id,
            limit=limit,
            offset=offset,
        )
    except SessionServiceError as exc:
        _raise_session_http_error(exc)

    return MessageListResponse(
        data=[
            MessageData(
                message_id=message.message_id,
                sequence_number=message.sequence_number,
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in messages
        ],
        pagination=PaginationData(
            limit=limit,
            offset=offset,
            total=total,
        ),
    )


@router.post(
    "/sessions/{session_id}/complete",
    response_model=SessionCompletionResponse,
    responses={
        404: {"description": "Session was not found."},
        409: {"description": "Unresolved interaction or invalid transition."},
        422: {"description": "Invalid completion reason."},
    },
)
def complete_session(
    session_id: str,
    body: CompleteSessionRequest,
    service: SessionService = Depends(get_session_service),
):
    """Complete a session and persist its transcript integrity hash.

    Repeated completion requests return the existing completion result.
    """

    try:
        session = service.complete_session(
            session_id,
            completed_at=_now_utc(),
            completion_reason=body.completion_reason,
        )
    except SessionServiceError as exc:
        _raise_session_http_error(exc)

    return SessionCompletionResponse(
        data=SessionCompletionData(
            session_id=session.session_id,
            status="completed",
            transcript_version=session.transcript_version,
            ended_at=session.ended_at,
        )
    )
