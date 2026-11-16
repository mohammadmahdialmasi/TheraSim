from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import llm as llm_routes


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