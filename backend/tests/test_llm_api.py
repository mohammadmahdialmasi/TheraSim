from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import llm as llm_routes
from app.core.config import PROVIDER_NAMES, ProviderConfig, Settings
from app.core.provider_settings import ProviderSettingsStore


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


class FakeOpenAIClient:
    def __init__(self, config, timeout=120):
        self.config = config
        self.timeout = timeout

    def get_models(self):
        return [{"id": "test-model", "owned_by": "test"}]

    def chat(self, model, messages, temperature=None, max_tokens=None):
        assert messages == [
            {"role": "user", "content": "Reply with OK."}
        ]
        return {"content": "OK", "model": model}


def test_provider_catalog_does_not_expose_credentials(monkeypatch):
    monkeypatch.setattr(
        llm_routes,
        "settings",
        Settings.from_environment({}),
    )
    response = client.get("/api/v1/llm/providers")

    assert response.status_code == 200

    data = response.json()

    assert data["active_provider"] == "ollama"
    assert len(data["providers"]) == 4
    assert {item["name"] for item in data["providers"]} == set(PROVIDER_NAMES)

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
        "llama_cpp": ProviderConfig(
            name="llama_cpp",
            base_url="http://127.0.0.1:8080/v1",
            model="",
            api_key="",
        ),
        "custom": ProviderConfig(
            name="custom",
            base_url="http://127.0.0.1:8000/v1",
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


def test_provider_settings_persist_without_returning_api_keys(
    monkeypatch, tmp_path
):
    configured = Settings.from_environment({})
    store = ProviderSettingsStore(
        configured,
        tmp_path / "provider-settings.json",
    )
    monkeypatch.setattr(llm_routes, "settings", configured)
    monkeypatch.setattr(llm_routes, "provider_settings_store", store)

    payload = {
        "active_provider": "llama_cpp",
        "providers": [
            {
                "name": name,
                "base_url": (
                    "http://127.0.0.1:9901/v1"
                    if name == "llama_cpp"
                    else configured.get_provider(name).base_url
                ),
                "model": "fictional-model" if name == "llama_cpp" else "",
                "api_key": "test-only-key" if name == "custom" else None,
            }
            for name in PROVIDER_NAMES
        ],
    }

    response = client.put(
        "/api/v1/llm/providers/settings",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["active_provider"] == "llama_cpp"
    assert response.json()["restart_required"] is True
    assert "test-only-key" not in response.text
    assert configured.get_provider("llama_cpp").base_url == (
        "http://127.0.0.1:9901/v1"
    )
    settings_response = client.get("/api/v1/llm/providers/settings")
    assert settings_response.status_code == 200
    settings_data = settings_response.json()
    custom_provider = next(
        item for item in settings_data["providers"] if item["name"] == "custom"
    )
    assert custom_provider["api_key_configured"] is True
    assert "test-only-key" not in settings_response.text

    restarted = Settings.from_environment({})
    ProviderSettingsStore(
        restarted,
        tmp_path / "provider-settings.json",
    ).load()
    assert restarted.llm_provider == "llama_cpp"
    assert restarted.get_provider("llama_cpp").model == "fictional-model"
    assert restarted.get_provider("custom").api_key == "test-only-key"


def test_provider_settings_reject_invalid_ports(monkeypatch, tmp_path):
    configured = Settings.from_environment({})
    monkeypatch.setattr(llm_routes, "settings", configured)
    monkeypatch.setattr(
        llm_routes,
        "provider_settings_store",
        ProviderSettingsStore(configured, tmp_path / "settings.json"),
    )
    payload = {
        "active_provider": "ollama",
        "providers": [
            {
                "name": name,
                "base_url": (
                    "http://127.0.0.1:65536/v1"
                    if name == "ollama"
                    else configured.get_provider(name).base_url
                ),
                "model": "",
            }
            for name in PROVIDER_NAMES
        ],
    }

    response = client.put("/api/v1/llm/providers/settings", json=payload)

    assert response.status_code == 422


def test_environment_values_override_persisted_provider_settings(
    monkeypatch,
    tmp_path,
):
    configured = Settings.from_environment({})
    store = ProviderSettingsStore(
        configured,
        tmp_path / "provider-settings.json",
    )
    store.update(
        active_provider="custom",
        providers=[
            {
                "name": name,
                "base_url": configured.get_provider(name).base_url,
                "model": f"saved-{name}",
                "api_key": None,
            }
            for name in PROVIDER_NAMES
        ],
    )

    for prefix in ("OLLAMA", "LM_STUDIO", "LLAMA_CPP", "CUSTOM_OPENAI"):
        for suffix in ("BASE_URL", "MODEL", "API_KEY"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)
    monkeypatch.delenv("THERASIM_LLM_PROVIDER", raising=False)
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:19001/v1",
    )
    monkeypatch.setenv("LM_STUDIO_MODEL", "environment-model")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "environment-key")
    monkeypatch.setenv("THERASIM_LLM_PROVIDER", "lm_studio")

    restarted = Settings.from_environment()
    ProviderSettingsStore(
        restarted,
        tmp_path / "provider-settings.json",
    ).load()

    assert restarted.llm_provider == "lm_studio"
    assert restarted.get_provider("ollama").base_url == (
        "http://127.0.0.1:19001/v1"
    )
    assert restarted.get_provider("lm_studio").model == "environment-model"
    assert restarted.get_provider("lm_studio").api_key == "environment-key"
    assert restarted.get_provider("custom").model == "saved-custom"


def test_test_connection_reports_supported_model_listing(monkeypatch):
    monkeypatch.setattr(
        llm_routes,
        "settings",
        Settings.from_environment({}),
    )
    monkeypatch.setattr(
        llm_routes,
        "OpenAICompatibleClient",
        FakeOpenAIClient,
    )

    response = client.post(
        "/api/v1/llm/providers/llama_cpp/test",
        json={
            "base_url": "http://127.0.0.1:8080/v1",
        },
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["success"] is True
    assert response.json()["model_listing_supported"] is True
    assert response.json()["models"][0]["id"] == "test-model"


def test_test_connection_verifies_the_selected_model(monkeypatch):
    monkeypatch.setattr(
        llm_routes,
        "OpenAICompatibleClient",
        FakeOpenAIClient,
    )

    response = client.post(
        "/api/v1/llm/providers/llama_cpp/test",
        json={
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "missing-model",
        },
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["success"] is False
    assert response.json()["status"] == "model_unavailable"
    assert response.json()["model_available"] is False


def test_test_connection_allows_manual_models_when_listing_is_missing(
    monkeypatch,
):
    class NoModelListingClient(FakeOpenAIClient):
        def get_models(self):
            from app.llm.client import ProviderResponseError

            raise ProviderResponseError(
                "custom returned HTTP 404.",
                status_code=404,
            )

    monkeypatch.setattr(
        llm_routes,
        "OpenAICompatibleClient",
        NoModelListingClient,
    )

    response = client.post(
        "/api/v1/llm/providers/custom/test",
        json={"base_url": "http://127.0.0.1:8000/v1"},
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["success"] is False
    assert response.json()["status"] == "model_required"
    assert response.json()["model_listing_supported"] is False
    assert response.json()["models"] == []


def test_test_connection_allows_server_method_not_supported(monkeypatch):
    class NoModelListingClient(FakeOpenAIClient):
        def get_models(self):
            from app.llm.client import ProviderResponseError

            raise ProviderResponseError(
                "custom returned HTTP 405.",
                status_code=405,
            )

    monkeypatch.setattr(
        llm_routes,
        "OpenAICompatibleClient",
        NoModelListingClient,
    )

    response = client.post(
        "/api/v1/llm/providers/custom/test",
        json={"base_url": "http://127.0.0.1:8000/v1"},
    )

    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["success"] is False
    assert response.json()["status"] == "model_required"
    assert response.json()["model_listing_supported"] is False


def test_test_connection_does_not_expose_provider_error_details(monkeypatch):
    class UnauthorizedClient(FakeOpenAIClient):
        def get_models(self):
            from app.llm.client import ProviderResponseError

            raise ProviderResponseError(
                "custom returned HTTP 401.",
                status_code=401,
            )

    monkeypatch.setattr(
        llm_routes,
        "OpenAICompatibleClient",
        UnauthorizedClient,
    )

    response = client.post(
        "/api/v1/llm/providers/custom/test",
        json={
            "base_url": "http://127.0.0.1:8000/v1",
            "api_key": "do-not-return-this-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["status"] == "authentication_failed"
    assert "do-not-return-this-key" not in response.text


def test_test_connection_refuses_remote_endpoint_in_local_only_mode(monkeypatch):
    monkeypatch.setattr(llm_routes.settings, "local_only_mode", True)

    response = client.post(
        "/api/v1/llm/providers/custom/test",
        json={"base_url": "https://models.example.test/v1"},
    )

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["status"] == "remote_blocked"


def test_remote_mode_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setattr(llm_routes.settings, "local_only_mode", True)
    providers = [
        {
            "name": name,
            "base_url": llm_routes.settings.get_provider(name).base_url,
            "model": "",
        }
        for name in PROVIDER_NAMES
    ]

    response = client.put(
        "/api/v1/llm/providers/settings",
        json={
            "active_provider": "ollama",
            "local_only": False,
            "providers": providers,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "explicit_remote_endpoint_confirmation_required"
    )


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


def test_hardware_assessment_is_requested_on_demand(monkeypatch):
    expected = {
        "operating_system": {"name": "Windows"},
        "recommendation_status": "inventory only",
    }
    monkeypatch.setattr(
        llm_routes,
        "assess_hardware",
        lambda **kwargs: expected,
    )

    response = client.get("/api/v1/llm/hardware")

    assert response.status_code == 200
    assert response.json() == expected


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