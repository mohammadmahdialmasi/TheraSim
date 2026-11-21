import base64
import json

import pytest

from app.core.config import PROVIDER_DEFAULTS, PROVIDER_NAMES, Settings
from app.core import provider_settings as provider_settings_module
from app.core.provider_settings import ProviderSettingsStore


@pytest.fixture
def isolated_provider_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for _, prefix in PROVIDER_DEFAULTS.values():
        for suffix in (
            "API_KEY",
            "BASE_URL",
            "MODEL",
            "PATIENT_MODEL",
            "EVALUATOR_MODEL",
        ):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)
    monkeypatch.delenv("THERASIM_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("THERASIM_LOCAL_ONLY", raising=False)


@pytest.fixture
def fake_credential_protection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        provider_settings_module,
        "protect_provider_key",
        lambda value: "protected::"
        + base64.b64encode(value.encode("utf-8")).decode("ascii"),
    )
    monkeypatch.setattr(
        provider_settings_module,
        "unprotect_provider_key",
        lambda value: base64.b64decode(
            value.removeprefix("protected::"),
            validate=True,
        ).decode("utf-8"),
    )


def _update_without_keys(store: ProviderSettingsStore) -> None:
    store.update(
        active_provider="custom",
        providers=[
            {
                "name": name,
                "base_url": store.settings.get_provider(name).base_url,
                "model": store.settings.get_provider(name).model,
                "api_key": None,
            }
            for name in PROVIDER_NAMES
        ],
    )


def test_environment_only_key_is_not_persisted_when_ui_omits_key(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_provider_environment: None,
) -> None:
    environment_key = "environment-only-test-key"
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", environment_key)
    path = tmp_path / "provider-settings.json"
    settings = Settings.from_environment({
        "CUSTOM_OPENAI_API_KEY": environment_key,
    })
    store = ProviderSettingsStore(settings, path)
    store.load()

    _update_without_keys(store)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert "api_key_protected" not in persisted["providers"]["custom"]
    assert "api_key" not in persisted["providers"]["custom"]
    assert environment_key not in path.read_text(encoding="utf-8")
    assert settings.get_provider("custom").api_key == environment_key


def test_explicit_ui_key_is_persisted_in_protected_form(
    tmp_path,
    isolated_provider_environment: None,
    fake_credential_protection: None,
) -> None:
    entered_key = "explicit-ui-test-key"
    settings = Settings.from_environment({})
    store = ProviderSettingsStore(
        settings,
        tmp_path / "provider-settings.json",
    )
    store.load()
    store.update(
        active_provider="custom",
        providers=[
            {
                "name": name,
                "base_url": settings.get_provider(name).base_url,
                "model": settings.get_provider(name).model,
                "api_key": entered_key if name == "custom" else None,
            }
            for name in PROVIDER_NAMES
        ],
    )

    content = (tmp_path / "provider-settings.json").read_text(
        encoding="utf-8"
    )
    persisted = json.loads(content)
    assert (
        persisted["providers"]["custom"]["api_key_protected"]
        == "protected::"
        + base64.b64encode(entered_key.encode("utf-8")).decode("ascii")
    )
    assert entered_key not in content
    assert settings.get_provider("custom").api_key == entered_key


def test_environment_key_remains_runtime_precedence_after_save(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_provider_environment: None,
    fake_credential_protection: None,
) -> None:
    saved_key = "previously-saved-test-key"
    environment_key = "environment-wins-test-key"
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", environment_key)
    path = tmp_path / "provider-settings.json"
    path.write_text(
        json.dumps(
            {
                "active_provider": "custom",
                "local_only": True,
                "providers": {
                    "custom": {
                        "base_url": "http://127.0.0.1:8000/v1",
                        "model": "",
                        "api_key_protected": (
                            provider_settings_module.protect_provider_key(
                                saved_key
                            )
                        ),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings.from_environment({})
    store = ProviderSettingsStore(settings, path)
    store.load()
    assert settings.get_provider("custom").api_key == environment_key

    _update_without_keys(store)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert (
        persisted["providers"]["custom"]["api_key_protected"]
        == provider_settings_module.protect_provider_key(saved_key)
    )
    assert settings.get_provider("custom").api_key == environment_key


def test_role_models_are_persisted_and_loaded_independently(
    tmp_path,
    isolated_provider_environment: None,
) -> None:
    path = tmp_path / "provider-settings.json"
    settings = Settings.from_environment({})
    store = ProviderSettingsStore(settings, path)
    store.load()

    providers = []
    for name in PROVIDER_NAMES:
        providers.append(
            {
                "name": name,
                "base_url": settings.get_provider(name).base_url,
                "model": "shared-model" if name == "ollama" else "",
                "patient_model": (
                    "client-model" if name == "ollama" else ""
                ),
                "evaluator_model": (
                    "evaluator-model" if name == "ollama" else ""
                ),
                "api_key": None,
            }
        )
    store.update(active_provider="ollama", providers=providers)

    reloaded = ProviderSettingsStore(Settings.from_environment({}), path)
    reloaded.load()

    assert reloaded.model_for_role("patient") == "client-model"
    assert reloaded.model_for_role("evaluator") == "evaluator-model"
    assert (
        reloaded.public_settings()["providers"][0]["patient_model"]
        == "client-model"
    )


def test_role_models_default_to_the_general_provider_model(
    tmp_path,
    isolated_provider_environment: None,
) -> None:
    settings = Settings.from_environment(
        {"OLLAMA_MODEL": "shared-model"}
    )
    store = ProviderSettingsStore(settings, tmp_path / "settings.json")
    store.load()

    assert store.model_for_role("patient") == "shared-model"
    assert store.model_for_role("evaluator") == "shared-model"
