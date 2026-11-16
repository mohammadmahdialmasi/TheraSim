from typing import Any

import httpx

from app.core.config import ProviderConfig


class ProviderConnectionError(Exception):
    """The local model server could not be reached."""


class ProviderResponseError(Exception):
    """The model server returned an invalid or unsuccessful response."""


class OpenAICompatibleClient:
    """Client for local OpenAI-compatible inference servers."""

    def __init__(
        self,
        config: ProviderConfig,
        timeout: float = 120,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.timeout = timeout
        self.transport = transport

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = (
            f"{self.config.base_url.rstrip('/')}/"
            f"{endpoint.lstrip('/')}"
        )

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if self.config.api_key:
            headers["Authorization"] = (
                f"Bearer {self.config.api_key}"
            )

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                )

        except httpx.TimeoutException as exc:
            raise ProviderConnectionError(
                f"{self.config.name} request timed out."
            ) from exc

        except httpx.RequestError as exc:
            raise ProviderConnectionError(
                f"{self.config.name} server is unavailable."
            ) from exc

        if not response.is_success:
            raise ProviderResponseError(
                f"{self.config.name} returned HTTP "
                f"{response.status_code}."
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError(
                f"{self.config.name} returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise ProviderResponseError(
                f"{self.config.name} returned an unexpected response."
            )

        return data

    def get_models(self) -> list[dict[str, str]]:
        data = self._request("GET", "models")
        if "data" not in data:
            raise ProviderResponseError(
                "Model list response is missing the data field."
            )

        raw_models = data["data"]

        if raw_models is None:
            return []

        if not isinstance(raw_models, list):
            raise ProviderResponseError(
                "Model list has an unexpected format."
            )

        models = []

        for item in raw_models:
            if not isinstance(item, dict):
                continue

            model_id = item.get("id")

            if not isinstance(model_id, str) or not model_id.strip():
                continue

            owner = item.get("owned_by", "unknown")

            models.append({
                "id": model_id,
                "owned_by": (
                    owner if isinstance(owner, str) else "unknown"
                ),
            })

        return models

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        if temperature is not None:
            payload["temperature"] = temperature

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        data = self._request(
            "POST",
            "chat/completions",
            payload,
        )

        choices = data.get("choices")

        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError(
                "Model response contains no completion choices."
            )

        first = choices[0]

        if not isinstance(first, dict):
            raise ProviderResponseError(
                "Model returned an invalid completion."
            )

        message = first.get("message")

        if not isinstance(message, dict):
            raise ProviderResponseError(
                "Model response does not contain a message."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError(
                f"{self.config.name} returned an empty final answer. "
                "Check the model output token budget and reasoning settings."
            )

        return {
            "content": content,
            "model": data.get("model", model),
            "finish_reason": first.get("finish_reason"),
            "usage": data.get("usage"),
        }