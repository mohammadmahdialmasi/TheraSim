from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import (
    ProviderName,
    settings,
)
from app.llm.client import (
    OpenAICompatibleClient,
    ProviderConnectionError,
    ProviderResponseError,
)


router = APIRouter(
    prefix="/api/v1/llm",
    tags=["LLM"],
)


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
    return OpenAICompatibleClient(
        config=settings.get_provider(name),
        timeout=settings.request_timeout_seconds,
    )


def handle_provider_error(exc: Exception) -> None:
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


@router.get("/providers")
def list_providers() -> dict:
    """Return configured providers without exposing API credentials."""

    providers = []

    for name in ("ollama", "lm_studio"):
        config = settings.get_provider(name)

        providers.append({
            "name": config.name,
            "base_url": config.base_url,
            "default_model": config.model or None,
            "is_active": name == settings.llm_provider,
        })

    return {
        "active_provider": settings.llm_provider,
        "providers": providers,
    }


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