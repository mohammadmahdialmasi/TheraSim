import pytest

from app.core.config import Settings


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


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings.from_environment({
            "THERASIM_LLM_PROVIDER": "unknown"
        })