from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import llm as llm_routes
from app.core.config import ProviderConfig


client = TestClient(app)


class FakeProvider:
    def get_models(self):
        return [
            {"id": "mock-model", "owned_by": "test"}
        ]

    def chat(self, model, messages, temperature=None, max_tokens=None):
        return {
            "content": "پاسخ آزمایشی مدل",
            "model": model,
            "finish_reason": "stop",
            "usage": None,
        }


def test_provider_catalog_does_not_expose_credentials():
    response = client.get("/api/v1/llm/providers")

    assert response.status_code == 200

    data = response.json()

    assert data["active_provider"] == "ollama"
    assert len(data["providers"]) == 2

    assert "api_key" not in str(data).lower()


def test_provider_catalog_exposes_only_provider_origin(monkeypatch):
    configs = {
        "ollama": ProviderConfig(
            name="ollama",
            base_url="https://user:secret@example.test:8443/private/path?token=secret",
            model="",
            api_key="",
        ),
        "lm_studio": ProviderConfig(
            name="lm_studio",
            base_url="http://127.0.0.1:1234/v1",
            model="",
            api_key="",
        ),
    }

    monkeypatch.setattr(
        llm_routes,
        "settings",
        type(
            "FakeSettings",
            (),
            {
                "llm_provider": "ollama",
                "get_provider": lambda _self, name: configs[name],
            },
        )(),
    )

    response = client.get("/api/v1/llm/providers")

    assert response.status_code == 200
    data = response.json()
    assert data["providers"][0]["base_url"] == "https://example.test:8443"
    assert "secret" not in response.text
    assert "/private" not in response.text


def test_model_list_endpoint(monkeypatch):
    fake = FakeProvider()

    monkeypatch.setattr(
        llm_routes,
        "get_provider",
        lambda name: fake,
    )

    response = client.get(
        "/api/v1/llm/models/lm_studio"
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "lm_studio"
    assert response.json()["models"][0]["id"] == "mock-model"


def test_chat_endpoint(monkeypatch):
    fake = FakeProvider()

    monkeypatch.setattr(
        llm_routes,
        "get_provider",
        lambda name: fake,
    )

    response = client.post(
        "/api/v1/llm/chat",
        json={
            "provider": "lm_studio",
            "model": "mock-model",
            "messages": [
                {
                    "role": "user",
                    "content": "سلام",
                }
            ],
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["provider"] == "lm_studio"
    assert data["model"] == "mock-model"
    assert data["message"]["content"] == "پاسخ آزمایشی مدل"


def test_chat_rejects_missing_model(monkeypatch):
    response = client.post(
        "/api/v1/llm/chat",
        json={
            "provider": "lm_studio",
            "messages": [
                {
                    "role": "user",
                    "content": "سلام",
                }
            ],
        },
    )

    assert response.status_code == 400