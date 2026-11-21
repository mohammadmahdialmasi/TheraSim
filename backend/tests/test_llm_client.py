import httpx
import pytest

from app.core.config import Settings
from app.llm.client import (
    OpenAICompatibleClient,
    ProviderResponseError,
)


def make_client(handler):
    config = Settings.from_environment({}).get_provider("ollama")

    return OpenAICompatibleClient(
        config=config,
        transport=httpx.MockTransport(handler),
    )


def test_model_list_is_parsed() -> None:
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/models"

        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "test-model", "owned_by": "local"}
                ]
            },
        )

    client = make_client(handler)

    assert client.get_models() == [
        {"id": "test-model", "owned_by": "local"}
    ]


def test_empty_model_list_returns_empty_list() -> None:
    def handler(request):
        return httpx.Response(
            200,
            json={"object": "list", "data": None},
        )

    client = make_client(handler)

    assert client.get_models() == []


def test_chat_completion_is_parsed() -> None:
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"

        payload = request.read().decode("utf-8")
        assert '"model":"test-model"' in payload.replace(" ", "")
        assert '"response_format"' in payload

        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello from a mock model.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 6,
                },
            },
        )

    client = make_client(handler)

    result = client.chat(
        model="test-model",
        messages=[
            {"role": "user", "content": "Hello"}
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "sample",
                "strict": True,
                "schema": {"type": "object"},
            },
        },
    )

    assert result["content"] == "Hello from a mock model."
    assert result["model"] == "test-model"
    assert result["finish_reason"] == "stop"


def test_json_schema_support_is_enabled_only_for_verified_provider():
    ollama_client = make_client(
        lambda request: httpx.Response(200, json={"data": []})
    )
    custom_config = Settings.from_environment({}).get_provider("custom")
    custom_client = OpenAICompatibleClient(
        config=custom_config,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": []})
        ),
    )

    assert ollama_client.supports_json_schema
    assert not custom_client.supports_json_schema


def test_empty_final_content_is_rejected_safely() -> None:
    hidden_reasoning = "PRIVATE_REASONING_NOT_FOR_USER"

    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": hidden_reasoning,
                        },
                        "finish_reason": "length",
                    }
                ]
            },
        )

    client = make_client(handler)

    with pytest.raises(ProviderResponseError) as error:
        client.chat(
            model="test-model",
            messages=[
                {"role": "user", "content": "Hello"}
            ],
        )

    assert "empty final answer" in str(error.value)
    assert hidden_reasoning not in str(error.value)


def test_invalid_model_response_is_rejected() -> None:
    def handler(request):
        return httpx.Response(200, json={"unexpected": []})

    client = make_client(handler)

    with pytest.raises(ProviderResponseError):
        client.get_models()