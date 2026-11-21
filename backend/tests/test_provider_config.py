import pytest

from app.core.config import PROVIDER_NAMES, Settings


def test_default_provider_is_ollama() -> None:
    config = Settings.from_environment({})

    assert config.llm_provider == "ollama"
    assert config.active_provider.base_url == (
        "http://127.0.0.1:11434/v1"
    )


def test_lm_studio_can_be_selected() -> None:
    config = Settings.from_environment({
        "THERASIM_LLM_PROVIDER": "lm_studio",
        "LM_STUDIO_MODEL": "test-model",
    })

    assert config.llm_provider == "lm_studio"
    assert config.active_provider.name == "lm_studio"
    assert config.active_provider.base_url == (
        "http://127.0.0.1:1234/v1"
    )
    assert config.active_provider.model == "test-model"


def test_all_provider_presets_default_to_loopback_without_api_keys() -> None:
    config = Settings.from_environment({})

    assert set(config.providers) == set(PROVIDER_NAMES)
    assert all(
        provider.base_url.startswith("http://127.0.0.1:")
        and not provider.api_key
        for provider in config.providers.values()
    )
    assert config.get_provider("llama_cpp").base_url == (
        "http://127.0.0.1:8080/v1"
    )
    assert config.get_provider("custom").base_url == (
        "http://127.0.0.1:8000/v1"
    )


@pytest.mark.parametrize(
    ("prefix", "provider", "url"),
    [
        ("OLLAMA", "ollama", "http://127.0.0.1:12401/v1"),
        ("LM_STUDIO", "lm_studio", "http://127.0.0.1:12402/v1"),
        ("LLAMA_CPP", "llama_cpp", "http://127.0.0.1:12403/v1"),
        ("CUSTOM_OPENAI", "custom", "http://127.0.0.1:12404/v1"),
    ],
)
def test_provider_specific_ports_are_editable(
    prefix: str,
    provider: str,
    url: str,
) -> None:
    config = Settings.from_environment({
        f"{prefix}_BASE_URL": url,
    })

    assert config.get_provider(provider).base_url == url


@pytest.mark.parametrize(
    "provider",
    ["ollama", "lm_studio", "llama_cpp", "custom"],
)
def test_each_provider_can_be_selected_from_environment(provider: str) -> None:
    config = Settings.from_environment({"THERASIM_LLM_PROVIDER": provider})

    assert config.llm_provider == provider
    assert config.active_provider.name == provider


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings.from_environment({
            "THERASIM_LLM_PROVIDER": "unknown"
        })


@pytest.mark.parametrize(
    "provider_url",
    [
        "ftp://localhost:1234/v1",
        "http://user:password@localhost:1234/v1",
        "http://localhost:1234/v1?token=secret",
        "http://localhost:1234/v1#fragment",
        "http://",
        "http://localhost:0/v1",
        "http://localhost:65536/v1",
        "http://192.168.1.25:8000/v1",
    ],
)
def test_invalid_or_credential_bearing_provider_urls_are_rejected(
    provider_url: str,
) -> None:
    with pytest.raises(ValueError, match="OLLAMA_BASE_URL"):
        Settings.from_environment({"OLLAMA_BASE_URL": provider_url})


def test_provider_url_is_normalized_without_trailing_slash() -> None:
    config = Settings.from_environment({
        "OLLAMA_BASE_URL": "https://localhost:11434/v1/",
    })

    assert config.active_provider.base_url == "https://localhost:11434/v1"


@pytest.mark.parametrize(
    "provider_url",
    [
        "http://localhost:8000/v1",
        "http://127.0.0.2:8000/v1",
        "http://[::1]:8000/v1",
        "https://models.example.test/v1",
    ],
)
def test_loopback_http_and_remote_https_are_supported(
    provider_url: str,
) -> None:
    config = Settings.from_environment({"OLLAMA_BASE_URL": provider_url})

    assert config.active_provider.base_url == provider_url