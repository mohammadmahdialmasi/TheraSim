from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Literal, NoReturn
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import (
    PROVIDER_NAMES,
    ProviderName,
    provider_url_origin_for_display,
    provider_url_is_loopback,
    settings,
    validate_provider_url,
)
from app.core.hardware import assess_hardware
from app.core.provider_settings import ProviderSettingsStore
from app.llm.client import (
    OpenAICompatibleClient,
    ProviderConnectionError,
    ProviderResponseError,
)


router = APIRouter(
    prefix="/api/v1/llm",
    tags=["LLM"],
)
provider_settings_store = ProviderSettingsStore(settings)

PROVIDER_LABELS: dict[ProviderName, str] = {
    "ollama": "Ollama",
    "lm_studio": "LM Studio",
    "llama_cpp": "llama.cpp server",
    "custom": "Custom OpenAI-compatible endpoint",
}


class ProviderSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ProviderName
    base_url: str = Field(min_length=1, max_length=2048)
    model: str = Field(default="", max_length=200)
    patient_model: str = Field(default="", max_length=200)
    evaluator_model: str = Field(default="", max_length=200)
    api_key: str | None = Field(default=None, max_length=2048)
    clear_api_key: bool = False

    @model_validator(mode="after")
    def validate_values(self) -> "ProviderSettingsInput":
        validate_provider_url(self.base_url)
        if any(
            char in model
            for model in (self.patient_model, self.evaluator_model)
            for char in "\x00\r\n"
        ):
            raise ValueError("Model identifiers contain invalid characters.")
        if self.api_key is not None and any(
            char in self.api_key for char in "\x00\r\n"
        ):
            raise ValueError("API key contains invalid characters.")
        return self


class ProviderSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_provider: ProviderName
    local_only: bool | None = None
    confirm_remote_endpoints: bool = False
    providers: list[ProviderSettingsInput] = Field(
        min_length=len(PROVIDER_NAMES),
        max_length=len(PROVIDER_NAMES),
    )

    @model_validator(mode="after")
    def validate_provider_set(self) -> "ProviderSettingsRequest":
        names = [item.name for item in self.providers]
        if set(names) != set(PROVIDER_NAMES) or len(names) != len(set(names)):
            raise ValueError("Settings for each provider must appear once.")
        return self


class ConnectionTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1, max_length=2048)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_values(self) -> "ConnectionTestRequest":
        validate_provider_url(self.base_url)
        if self.api_key is not None and any(
            char in self.api_key for char in "\x00\r\n"
        ):
            raise ValueError("API key contains invalid characters.")
        return self


def _settings_store(request: Request) -> ProviderSettingsStore:
    store = getattr(request.app.state, "provider_settings_store", None)
    return store if isinstance(store, ProviderSettingsStore) else provider_settings_store


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderName | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)

    messages: list[ChatMessage] = Field(
        min_length=1,
        max_length=100,
    )

    temperature: float | None = Field(
        default=None,
        ge=0,
        le=2,
    )

    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=32768,
    )


def get_provider(
    name: ProviderName,
) -> OpenAICompatibleClient:
    config = settings.get_provider(name)
    if settings.local_only_mode and not provider_url_is_loopback(config.base_url):
        raise HTTPException(
            status_code=403,
            detail="remote_provider_blocked_by_local_only_mode",
        )
    return OpenAICompatibleClient(
        config=config,
        timeout=settings.request_timeout_seconds,
    )


def handle_provider_error(exc: Exception) -> NoReturn:
    if isinstance(exc, ProviderConnectionError):
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    if isinstance(exc, ProviderResponseError):
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=502,
        detail="Local model provider request failed.",
    ) from exc


def _connection_test_result(
    request: Request,
    provider: ProviderName,
    *,
    connected: bool,
    success: bool,
    status: str,
    model_listing_supported: bool,
    model_available: bool | None,
    models: list[dict[str, str]],
) -> dict[str, object]:
    result: dict[str, object] = {
        "provider": provider,
        "connected": connected,
        "success": success,
        "status": status,
        "model_listing_supported": model_listing_supported,
        "model_available": model_available,
        "models": models,
    }
    results = getattr(request.app.state, "provider_test_results", None)
    if not isinstance(results, dict):
        results = {}
        request.app.state.provider_test_results = results
    results[provider] = {
        "tested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "success": success,
        "status": status,
        "model_available": model_available,
    }
    return result


@router.get("/providers")
def list_providers() -> dict:
    """Return configured providers without exposing API credentials."""

    providers = []

    for name in PROVIDER_NAMES:
        config = settings.get_provider(name)

        providers.append({
            "name": config.name,
            "label": PROVIDER_LABELS[name],
            "base_url": provider_url_origin_for_display(config.base_url),
            "default_model": config.model or None,
            "is_active": name == settings.llm_provider,
        })

    return {
        "active_provider": settings.llm_provider,
        "providers": providers,
    }


@router.get("/providers/settings")
def read_provider_settings(request: Request) -> dict[str, object]:
    """Return endpoint settings without returning API-key values."""

    return _settings_store(request).public_settings()


@router.put("/providers/settings")
def save_provider_settings(
    payload: ProviderSettingsRequest,
    request: Request,
) -> dict[str, object]:
    """Validate and persist all provider settings outside the databases."""

    store = _settings_store(request)
    try:
        local_only = (
            settings.local_only_mode
            if payload.local_only is None
            else payload.local_only
        )
        if not local_only and not payload.confirm_remote_endpoints:
            raise HTTPException(
                status_code=400,
                detail="explicit_remote_endpoint_confirmation_required",
            )
        store.update(
            active_provider=payload.active_provider,
            providers=[
                item.model_dump(exclude_unset=True)
                for item in payload.providers
            ],
            local_only=local_only,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail="Provider settings could not be saved.",
        ) from exc

    return {
        **store.public_settings(),
        "restart_required": True,
    }


@router.post("/providers/{provider_name}/test")
def test_provider_connection(
    provider_name: ProviderName,
    payload: ConnectionTestRequest,
    request: Request,
) -> dict[str, object]:
    """Test endpoint access, provider authentication, and model availability."""

    base_url = validate_provider_url(payload.base_url)
    if settings.local_only_mode and not provider_url_is_loopback(base_url):
        return _connection_test_result(
            request,
            provider_name,
            connected=False,
            success=False,
            status="remote_blocked",
            model_listing_supported=False,
            model_available=None,
            models=[],
        )

    config = settings.get_provider(provider_name)
    test_config = type(config)(
        name=provider_name,
        base_url=base_url,
        model=payload.model or config.model,
        api_key=payload.api_key if payload.api_key is not None else config.api_key,
    )
    provider = OpenAICompatibleClient(
        config=test_config,
        timeout=settings.request_timeout_seconds,
    )
    try:
        models = provider.get_models()
    except ProviderResponseError as exc:
        if exc.status_code in {401, 403}:
            return _connection_test_result(
                request,
                provider_name,
                connected=False,
                success=False,
                status="authentication_failed",
                model_listing_supported=False,
                model_available=None,
                models=[],
            )
        if exc.status_code in {404, 405, 501}:
            model = test_config.model
            if not model:
                return _connection_test_result(
                    request,
                    provider_name,
                    connected=True,
                    success=False,
                    status="model_required",
                    model_listing_supported=False,
                    model_available=None,
                    models=[],
                )
            try:
                provider.chat(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": "Reply with OK.",
                        }
                    ],
                    temperature=0,
                    max_tokens=8,
                )
            except ProviderConnectionError as chat_error:
                return _connection_test_result(
                    request,
                    provider_name,
                    connected=False,
                    success=False,
                    status=chat_error.reason,
                    model_listing_supported=False,
                    model_available=None,
                    models=[],
                )
            except ProviderResponseError as chat_error:
                status = (
                    "authentication_failed"
                    if chat_error.status_code in {401, 403}
                    else "model_unavailable"
                    if chat_error.status_code in {400, 404, 422}
                    else "provider_error"
                )
                return _connection_test_result(
                    request,
                    provider_name,
                    connected=False,
                    success=False,
                    status=status,
                    model_listing_supported=False,
                    model_available=(
                        False if status == "model_unavailable" else None
                    ),
                    models=[],
                )
            return _connection_test_result(
                request,
                provider_name,
                connected=True,
                success=True,
                status="model_available",
                model_listing_supported=False,
                model_available=True,
                models=[],
            )
        return _connection_test_result(
            request,
            provider_name,
            connected=False,
            success=False,
            status=(
                "authentication_failed"
                if exc.status_code in {401, 403}
                else "provider_error"
            ),
            model_listing_supported=False,
            model_available=None,
            models=[],
        )
    except ProviderConnectionError as exc:
        return _connection_test_result(
            request,
            provider_name,
            connected=False,
            success=False,
            status=exc.reason,
            model_listing_supported=False,
            model_available=None,
            models=[],
        )

    model = test_config.model
    if model:
        model_available = any(item["id"] == model for item in models)
        if not model_available:
            return _connection_test_result(
                request,
                provider_name,
                connected=True,
                success=False,
                status="model_unavailable",
                model_listing_supported=True,
                model_available=False,
                models=models,
            )
    else:
        model_available = None

    return _connection_test_result(
        request,
        provider_name,
        connected=True,
        success=True,
        status="connected",
        model_listing_supported=True,
        model_available=model_available,
        models=models,
    )


@router.get("/models/{provider_name}")
def list_models(provider_name: ProviderName) -> dict:
    """Retrieve models exposed by the selected local provider."""

    provider = get_provider(provider_name)

    try:
        models = provider.get_models()
    except (ProviderConnectionError, ProviderResponseError) as exc:
        handle_provider_error(exc)

    return {
        "provider": provider_name,
        "models": models,
    }


@router.get("/hardware")
def read_hardware_assessment() -> dict[str, object]:
    """Collect optional local hardware facts without selecting or downloading a model."""

    ollama_url = settings.get_provider("ollama").base_url
    parsed_url = urlsplit(ollama_url)
    ollama_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
    app_data_root = Path(
        os.environ.get("LOCALAPPDATA", str(Path.home()))
    ) / "TheraSim"
    return assess_hardware(
        data_directory=app_data_root,
        ollama_base_url=ollama_origin,
    )


@router.post("/chat")
def create_chat_completion(request: ChatRequest) -> dict:
    """Send a non-streaming chat completion to a local model."""

    provider_name = request.provider or settings.llm_provider
    provider_config = settings.get_provider(provider_name)

    model = request.model or provider_config.model

    if not model:
        raise HTTPException(
            status_code=400,
            detail=(
                "No model selected. Provide a model ID or configure "
                "a default model for this provider."
            ),
        )

    provider = get_provider(provider_name)

    messages = [
        item.model_dump()
        for item in request.messages
    ]

    try:
        result = provider.chat(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except (ProviderConnectionError, ProviderResponseError) as exc:
        handle_provider_error(exc)

    return {
        "provider": provider_name,
        "model": result["model"],
        "message": {
            "role": "assistant",
            "content": result["content"],
        },
        "finish_reason": result["finish_reason"],
        "usage": result["usage"],
    }