"""Local single-reviewer account setup and bearer-session endpoints."""

import ipaddress
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.services.local_auth import (
    AuthenticatedUser,
    AuthSession,
    LocalAuthAlreadyInitializedError,
    LocalAuthError,
    LocalAuthInvalidCredentialsError,
    LocalAuthRateLimitedError,
    LocalAuthInvalidPasswordError,
    LocalAuthInvalidReviewerNameError,
    LocalAuthService,
    LocalAuthTokenError,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Local Authentication"])
_bearer = HTTPBearer(auto_error=False)


class AuthStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initialized: bool


class AuthStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuthStatusData


class InitializeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reviewer_name: StrictStr = Field(min_length=1, max_length=80)
    password: StrictStr = Field(min_length=12, max_length=1024)

    @field_validator("reviewer_name")
    @classmethod
    def validate_reviewer_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Reviewer name must not be blank.")
        return value.strip()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    password: StrictStr = Field(min_length=1, max_length=1024)


class AuthenticatedUserData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    reviewer_name: str


class AuthSessionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: AuthenticatedUserData


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuthSessionData


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuthenticatedUserData


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: dict[str, bool]


def get_local_auth_service(request: Request) -> LocalAuthService:
    service = getattr(request.app.state, "local_auth_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="local_auth_service_unavailable",
        )
    return service


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    service = get_local_auth_service(request)
    try:
        return service.authenticate(credentials.credentials)
    except LocalAuthTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def _raise_auth_error(error: LocalAuthError) -> NoReturn:
    if isinstance(error, LocalAuthAlreadyInitializedError):
        raise HTTPException(status_code=409, detail="account_already_initialized") from None
    if isinstance(
        error,
        (LocalAuthInvalidPasswordError, LocalAuthInvalidReviewerNameError),
    ):
        raise HTTPException(status_code=422, detail="invalid_initialization_input") from None
    if isinstance(error, LocalAuthInvalidCredentialsError):
        raise HTTPException(
            status_code=401,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    if isinstance(error, LocalAuthRateLimitedError):
        raise HTTPException(
            status_code=429,
            detail="login_rate_limited",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from None
    raise HTTPException(status_code=500, detail="local_authentication_error") from None


def _session_data(session: AuthSession) -> AuthSessionData:
    return AuthSessionData(
        access_token=session.token,
        expires_at=session.expires_at,
        user=AuthenticatedUserData(
            user_id=session.user.user_id,
            reviewer_name=session.user.reviewer_name,
        ),
    )


def _require_loopback(request: Request) -> None:
    client = request.client
    if client is None:
        raise HTTPException(status_code=403, detail="loopback_setup_required")
    if client.host == "testclient":
        return
    try:
        is_loopback = ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise HTTPException(status_code=403, detail="loopback_setup_required")


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(
    service: LocalAuthService = Depends(get_local_auth_service),
) -> AuthStatusResponse:
    return AuthStatusResponse(
        data=AuthStatusData(initialized=service.is_initialized())
    )


@router.post(
    "/initialize",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def initialize_local_account(
    request: Request,
    payload: InitializeRequest,
    service: LocalAuthService = Depends(get_local_auth_service),
) -> AuthSessionResponse:
    _require_loopback(request)
    try:
        session = service.initialize(
            reviewer_name=payload.reviewer_name,
            password=payload.password,
        )
    except LocalAuthError as exc:
        _raise_auth_error(exc)
    return AuthSessionResponse(data=_session_data(session))


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    service: LocalAuthService = Depends(get_local_auth_service),
) -> AuthSessionResponse:
    try:
        client_key = (
            request.client.host
            if request.client is not None
            else "unknown-client"
        )
        session = service.login(
            password=payload.password,
            client_key=client_key,
        )
    except LocalAuthError as exc:
        _raise_auth_error(exc)
    return AuthSessionResponse(data=_session_data(session))


@router.get("/me", response_model=AuthUserResponse)
def current_user(
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthUserResponse:
    return AuthUserResponse(
        data=AuthenticatedUserData(
            user_id=user.user_id,
            reviewer_name=user.reviewer_name,
        )
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    _user: AuthenticatedUser = Depends(get_current_user),
) -> LogoutResponse:
    if credentials is None:
        raise HTTPException(status_code=401, detail="authentication_required")
    get_local_auth_service(request).logout(credentials.credentials)
    return LogoutResponse(data={"logged_out": True})
