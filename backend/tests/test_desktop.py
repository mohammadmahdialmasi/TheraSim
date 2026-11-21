from pathlib import Path

import pytest

from app.core.paths import project_root
from app.desktop import _open_browser, load_local_config, user_data_dir


def test_local_config_loads_only_allowlisted_values(tmp_path: Path) -> None:
    config = tmp_path / "config.env"
    config.write_text(
        "# Local model settings\n"
        'THERASIM_LLM_PROVIDER="ollama"\n'
        "OLLAMA_MODEL=synthetic-model\n",
        encoding="utf-8",
    )
    environment = {"OLLAMA_MODEL": "environment-model"}

    load_local_config(config, environment)

    assert environment == {
        "THERASIM_LLM_PROVIDER": "ollama",
        "OLLAMA_MODEL": "environment-model",
    }


@pytest.mark.parametrize(
    "contents",
    [
        "UNKNOWN_SETTING=value\n",
        "not-an-assignment\n",
        "OLLAMA_MODEL=unsafe\x00value\n",
    ],
)
def test_local_config_rejects_malformed_or_unsupported_entries(
    tmp_path: Path,
    contents: str,
) -> None:
    config = tmp_path / "config.env"
    config.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError):
        load_local_config(config, {})


def test_user_data_dir_is_scoped_to_local_app_data() -> None:
    assert user_data_dir({"LOCALAPPDATA": r"C:\Users\demo\AppData\Local"}) == (
        Path(r"C:\Users\demo\AppData\Local") / "TheraSim"
    )


def test_source_resource_root_contains_current_act_rubric() -> None:
    assert (
        project_root() / "rubrics" / "act" / "ACT_RUBRIC_V0.json"
    ).is_file()


def test_browser_can_be_disabled_for_headless_package_smoke(
    monkeypatch,
) -> None:
    def unexpected_browser_open(_url: str) -> bool:
        raise AssertionError("The headless check must not open a browser.")

    monkeypatch.setenv("THERASIM_OPEN_BROWSER", "0")
    monkeypatch.setattr("app.desktop.webbrowser.open", unexpected_browser_open)

    _open_browser("http://127.0.0.1:8765/")
