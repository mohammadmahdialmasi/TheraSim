"""Simulation run lifecycle API endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.routes.cases import get_case_service
from app.core.config import settings
from app.persistence.repositories.simulation_runs import (
    SESSION_PLANNING_POLICIES,
)
from app.services.cases import CaseService
from app.services.runs import (
    DEFAULT_EVALUATION_RUBRIC_ID,
    DEFAULT_EVALUATION_RUBRIC_VERSION,
    DEFAULT_PROTOCOL_ID,
    DEFAULT_PROTOCOL_VERSION,
    RestrictedProfileNotFoundError,
    RunCaseInactiveError,
    RunCaseNotFoundError,
    RunCaseVersionNotFoundError,
    RunConflictError,
    RunNotFoundError,
    RunProtocolConfigurationError,
    RunService,
    RunServiceError,
    RunStateTransitionError,
    SimulationRunRecord,
)
from app.services.sessions import SessionService


router = APIRouter(
    prefix="/api/v1/simulation-runs",
    tags=["Simulation Runs"],
)


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=200)
    case_version_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    modality: str = Field(min_length=1, max_length=50)
    language: str = Field(min_length=2, max_length=20)
    protocol_id: str = Field(
        default=DEFAULT_PROTOCOL_ID,
        min_length=1,
        max_length=100,
    )
    protocol_version: str = Field(
        default=DEFAULT_PROTOCOL_VERSION,
        min_length=1,
        max_length=50,
    )
    session_planning_policy: str = "flexible"
    evaluation_rubric_id: str = Field(
        default=DEFAULT_EVALUATION_RUBRIC_ID,
        min_length=1,
        max_length=100,
    )
    evaluation_rubric_version: str = Field(
        default=DEFAULT_EVALUATION_RUBRIC_VERSION,
        min_length=1,
        max_length=50,
    )

    @field_validator(
        "case_id",
        "modality",
        "language",
        "protocol_id",
        "protocol_version",
        "evaluation_rubric_id",
        "evaluation_rubric_version",
    )
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field cannot be blank.")
        return value.strip()

    @field_validator("session_planning_policy")
    @classmethod
    def validate_planning_policy(cls, value: str) -> str:
        if value not in SESSION_PLANNING_POLICIES:
            raise ValueError("Unsupported session planning policy.")
        return value

    @field_validator("case_version_id")
    @classmethod
    def validate_optional_version(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Case version ID cannot be blank.")
        return value.strip() if value is not None else None


class RunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    case_id: str
    case_version_id: str
    modality: str
    language: str
    status: str
    session_count: int
    protocol_id: str
    protocol_version: str
    session_planning_policy: str
    evaluation_rubric_id: str
    evaluation_rubric_version: str
    started_at: str | None
    completed_at: str | None
    created_at: str


class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: RunData


class RunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[RunData]


def get_run_service(request: Request) -> RunService:
    service = getattr(request.app.state, "run_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="run_service_unavailable",
        )

    return service


def get_session_service(request: Request) -> SessionService:
    service = getattr(request.app.state, "session_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="session_service_unavailable",
        )

    return service


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _run_response(
    run: SimulationRunRecord,
    session_service: SessionService,
) -> RunResponse:
    sessions = session_service.list_sessions(run.run_id)

    return RunResponse(
        data=RunData(
            run_id=run.run_id,
            case_id=run.case_id,
            case_version_id=run.case_version_id,
            modality=run.modality,
            language=run.language,
            status=run.status,
            session_count=len(sessions),
            protocol_id=run.protocol_id,
            protocol_version=run.protocol_version,
            session_planning_policy=run.session_planning_policy,
            evaluation_rubric_id=run.evaluation_rubric_id,
            evaluation_rubric_version=run.evaluation_rubric_version,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
    )


def _raise_run_http_error(exc: RunServiceError) -> None:
    if isinstance(exc, RunNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        ) from None

    if isinstance(exc, RunCaseNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="case_not_found",
        ) from None

    if isinstance(exc, RunCaseInactiveError):
        raise HTTPException(
            status_code=409,
            detail="case_not_active",
        ) from None

    if isinstance(exc, RunCaseVersionNotFoundError):
        raise HTTPException(
            status_code=422,
            detail="case_version_not_found",
        ) from None

    if isinstance(exc, RunProtocolConfigurationError):
        raise HTTPException(
            status_code=422,
            detail="therapy_protocol_configuration_unsupported",
        ) from None

    if isinstance(exc, RestrictedProfileNotFoundError):
        raise HTTPException(
            status_code=409,
            detail="restricted_case_configuration_incomplete",
        ) from None

    if isinstance(exc, RunConflictError):
        raise HTTPException(
            status_code=409,
            detail="simulation_run_conflict",
        ) from None

    if isinstance(exc, RunStateTransitionError):
        raise HTTPException(
            status_code=409,
            detail="invalid_run_state_transition",
        ) from None

    raise HTTPException(
        status_code=500,
        detail="simulation_run_service_error",
    ) from None


def _select_case_version(
    *,
    request: CreateRunRequest,
    case_service: CaseService,
):
    case = case_service.get_case(request.case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="case_not_found",
        )

    if case.status != "active":
        raise HTTPException(
            status_code=409,
            detail="case_not_active",
        )

    versions = case_service.list_case_versions(request.case_id)

    matching_versions = [
        version
        for version in versions
        if version.modality.casefold() == request.modality.casefold()
        and version.language.casefold() == request.language.casefold()
        and case_service.get_public_profile(
            version.case_version_id
        ) is not None
    ]

    if request.case_version_id is not None:
        selected = next(
            (
                version
                for version in matching_versions
                if version.case_version_id == request.case_version_id
            ),
            None,
        )

        if selected is None:
            raise HTTPException(
                status_code=422,
                detail="case_version_not_compatible_or_not_public",
            )

        return selected

    if not matching_versions:
        raise HTTPException(
            status_code=422,
            detail="case_version_not_available",
        )

    if len(matching_versions) > 1:
        raise HTTPException(
            status_code=409,
            detail="case_version_selection_required",
        )

    return matching_versions[0]


@router.post(
    "",
    response_model=RunResponse,
    status_code=201,
    responses={
        404: {"description": "Case was not found."},
        409: {"description": "Case or run configuration conflict."},
        422: {"description": "Invalid or unavailable case version."},
        503: {"description": "Run service is unavailable."},
    },
)
def create_simulation_run(
    body: CreateRunRequest,
    run_service: RunService = Depends(get_run_service),
    case_service: CaseService = Depends(get_case_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Create an initialized run using an explicitly public case version."""

    selected_version = _select_case_version(
        request=body,
        case_service=case_service,
    )

    try:
        run = run_service.create_run(
            run_id=str(uuid4()),
            case_id=body.case_id,
            case_version_id=selected_version.case_version_id,
            configuration_version=settings.app_version,
            created_at=_now_utc(),
            protocol_id=body.protocol_id,
            protocol_version=body.protocol_version,
            session_planning_policy=body.session_planning_policy,
            evaluation_rubric_id=body.evaluation_rubric_id,
            evaluation_rubric_version=body.evaluation_rubric_version,
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return _run_response(run, session_service)


@router.get(
    "",
    response_model=RunListResponse,
)
def list_simulation_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, min_length=1, max_length=30),
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """List persisted simulation runs for local workspace recovery."""

    try:
        runs = run_service.list_runs(
            status=status,
            limit=limit,
            offset=offset,
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return RunListResponse(
        data=[
            _run_response(run, session_service).data
            for run in runs
        ]
    )


@router.get(
    "/{run_id}",
    response_model=RunResponse,
)
def get_simulation_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Retrieve authorized simulation metadata."""

    run = run_service.get_run(run_id)

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        )

    return _run_response(run, session_service)


@router.post(
    "/{run_id}/start",
    response_model=RunResponse,
    responses={
        404: {"description": "Simulation run was not found."},
        409: {"description": "Invalid run state transition."},
    },
)
def start_simulation_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Start an initialized simulation run."""

    try:
        run = run_service.start_run(
            run_id,
            started_at=_now_utc(),
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return _run_response(run, session_service)


@router.post(
    "/{run_id}/interrupt",
    response_model=RunResponse,
    responses={
        404: {"description": "Simulation run was not found."},
        409: {"description": "Invalid run state transition."},
    },
)
def interrupt_simulation_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Interrupt an active simulation run."""

    try:
        run = run_service.interrupt_run(
            run_id,
            interrupted_at=_now_utc(),
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return _run_response(run, session_service)


@router.post(
    "/{run_id}/resume",
    response_model=RunResponse,
    responses={
        404: {"description": "Simulation run was not found."},
        409: {"description": "Invalid run state transition."},
    },
)
def resume_simulation_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Resume an interrupted simulation run."""

    try:
        run = run_service.resume_run(
            run_id,
            resumed_at=_now_utc(),
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return _run_response(run, session_service)


@router.post(
    "/{run_id}/complete",
    response_model=RunResponse,
    responses={
        404: {"description": "Simulation run was not found."},
        409: {
            "description": (
                "The run cannot be completed in its current state "
                "or its created sessions are not all completed."
            )
        },
    },
)
def complete_simulation_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_service: SessionService = Depends(get_session_service),
):
    """Complete a run after its created sessions have been completed."""

    try:
        run = run_service.complete_run(
            run_id,
            completed_at=_now_utc(),
        )
    except RunServiceError as exc:
        _raise_run_http_error(exc)

    return _run_response(run, session_service)
