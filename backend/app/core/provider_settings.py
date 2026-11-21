"""Persist per-provider OpenAI-compatible endpoint settings outside SQLite."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Mapping, cast
from urllib.parse import urlsplit

from app.core.config import (
    PROVIDER_NAMES,
    PROVIDER_DEFAULTS,
    ProviderName,
    Settings,
    provider_url_origin_for_display,
    validate_provider_url,
)
from app.core.credential_store import (
    protect_provider_key,
    unprotect_provider_key,
)


def provider_settings_path(
    env: Mapping[str, str] | None = None,
) -> Path:
    source = os.environ if env is None else env
    explicit_path = source.get("THERASIM_PROVIDER_SETTINGS_PATH")
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()

    local_app_data = source.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).expanduser() / "TheraSim" / "provider-settings.json"

    config_home = source.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "TheraSim" / "provider-settings.json"

    return Path.home() / ".config" / "TheraSim" / "provider-settings.json"


class ProviderSettingsStore:
    """Load and atomically persist provider settings without database changes."""

    def __init__(
        self,
        settings: Settings,
        path: Path | str | None = None,
    ) -> None:
        self.settings = settings
        self.path = Path(path).expanduser().resolve() if path else None
        self._lock = RLock()
        self._saved_api_keys: dict[ProviderName, str] | None = None
        self._patient_models: dict[ProviderName, str] = {
            name: "" for name in PROVIDER_NAMES
        }
        self._evaluator_models: dict[ProviderName, str] = {
            name: "" for name in PROVIDER_NAMES
        }

    def _path(self) -> Path:
        return self.path or provider_settings_path()

    def load(self) -> None:
        path = self._path()
        if not path.exists():
            self._saved_api_keys = {name: "" for name in PROVIDER_NAMES}
            for name in PROVIDER_NAMES:
                prefix = PROVIDER_DEFAULTS[name][1]
                self._patient_models[name] = os.environ.get(
                    f"{prefix}_PATIENT_MODEL",
                    "",
                ).strip()
                self._evaluator_models[name] = os.environ.get(
                    f"{prefix}_EVALUATOR_MODEL",
                    "",
                ).strip()
            return
        if not path.is_file():
            raise ValueError("Provider settings path must be a regular file.")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Saved provider settings could not be read.") from exc

        if not isinstance(data, dict):
            raise ValueError("Saved provider settings have an invalid format.")

        active_provider = data.get("active_provider")
        providers = data.get("providers")
        local_only_mode = data.get("local_only", True)
        if active_provider not in PROVIDER_NAMES or not isinstance(providers, dict):
            raise ValueError("Saved provider settings have an invalid format.")
        if not isinstance(local_only_mode, bool):
            raise ValueError("Saved provider settings have an invalid format.")

        migrated_plaintext_key = False
        saved_api_keys: dict[ProviderName, str] = {
            name: "" for name in PROVIDER_NAMES
        }
        with self._lock:
            for name in PROVIDER_NAMES:
                item = providers.get(name)
                if item is None:
                    continue
                if not isinstance(item, dict):
                    raise ValueError("Saved provider settings have an invalid format.")
                base_url = item.get("base_url")
                model = item.get("model", "")
                patient_model = item.get("patient_model", "")
                evaluator_model = item.get("evaluator_model", "")
                legacy_api_key = item.get("api_key", "")
                protected_api_key = item.get("api_key_protected", "")
                if (
                    not isinstance(base_url, str)
                    or not isinstance(model, str)
                    or not isinstance(patient_model, str)
                    or not isinstance(evaluator_model, str)
                    or not isinstance(legacy_api_key, str)
                    or not isinstance(protected_api_key, str)
                    or len(model) > 200
                    or len(patient_model) > 200
                    or len(evaluator_model) > 200
                    or len(legacy_api_key) > 2048
                    or len(protected_api_key) > 8192
                    or any(char in patient_model for char in "\x00\r\n")
                    or any(char in evaluator_model for char in "\x00\r\n")
                    or any(char in legacy_api_key for char in "\x00\r\n")
                ):
                    raise ValueError("Saved provider settings have an invalid format.")
                if legacy_api_key:
                    protected_api_key = protect_provider_key(legacy_api_key)
                    item.pop("api_key", None)
                    item["api_key_protected"] = protected_api_key
                    migrated_plaintext_key = True
                stored_api_key = (
                    unprotect_provider_key(protected_api_key)
                    if protected_api_key
                    else ""
                )
                saved_api_keys[name] = stored_api_key
                env_prefix = PROVIDER_DEFAULTS[name][1]
                self._patient_models[name] = os.environ.get(
                    f"{env_prefix}_PATIENT_MODEL",
                    patient_model,
                ).strip()
                self._evaluator_models[name] = os.environ.get(
                    f"{env_prefix}_EVALUATOR_MODEL",
                    evaluator_model,
                ).strip()
                self.settings.update_provider(
                    name,
                    base_url=os.environ.get(
                        f"{env_prefix}_BASE_URL",
                        base_url,
                    ),
                    model=os.environ.get(
                        f"{env_prefix}_MODEL",
                        model,
                    ),
                    api_key=os.environ.get(
                        f"{env_prefix}_API_KEY",
                        stored_api_key,
                    ),
                )
            provider_override = os.environ.get("THERASIM_LLM_PROVIDER")
            if provider_override is not None:
                provider_override = provider_override.strip().lower()
                if provider_override not in PROVIDER_NAMES:
                    raise ValueError(
                        "THERASIM_LLM_PROVIDER has an invalid value."
                    )
                active_provider = cast(ProviderName, provider_override)
            self.settings.llm_provider = active_provider
            local_only_override = os.environ.get("THERASIM_LOCAL_ONLY")
            if local_only_override is not None:
                local_only_value = local_only_override.strip().lower()
                if local_only_value not in {
                    "1", "true", "yes", "on", "0", "false", "no", "off"
                }:
                    raise ValueError("THERASIM_LOCAL_ONLY has an invalid value.")
                local_only_mode = local_only_value in {
                    "1", "true", "yes", "on"
                }
            self.settings.local_only_mode = local_only_mode
            if migrated_plaintext_key:
                self._write(data)
            self._saved_api_keys = saved_api_keys

    def public_settings(self) -> dict[str, object]:
        with self._lock:
            providers = []
            for name in PROVIDER_NAMES:
                config = self.settings.get_provider(name)
                parsed_url = validate_provider_url(config.base_url)
                parsed = urlsplit(parsed_url)
                providers.append(
                    {
                        "name": name,
                        "base_url": parsed_url,
                        "host": parsed.hostname or "127.0.0.1",
                        "port": parsed.port or (
                            443 if parsed.scheme == "https" else 80
                        ),
                        "api_base_path": parsed.path or "",
                        "model": config.model,
                        "patient_model": self._patient_models[name],
                        "evaluator_model": self._evaluator_models[name],
                        "api_key_configured": bool(config.api_key),
                    }
                )
            return {
                "active_provider": self.settings.llm_provider,
                "local_only": self.settings.local_only_mode,
                "providers": providers,
            }

    def update(
        self,
        *,
        active_provider: ProviderName,
        providers: list[dict[str, object]],
        local_only: bool | None = None,
    ) -> None:
        if active_provider not in PROVIDER_NAMES:
            raise ValueError("Unknown model provider.")
        if local_only is not None and not isinstance(local_only, bool):
            raise ValueError("Local-only mode must be a boolean.")

        normalized: dict[
            ProviderName,
            tuple[str, str, str, str, str | None, bool],
        ] = {}
        for item in providers:
            name = item.get("name")
            base_url = item.get("base_url")
            model = item.get("model", "")
            patient_model = item.get("patient_model")
            evaluator_model = item.get("evaluator_model")
            api_key = item.get("api_key")
            clear_api_key = item.get("clear_api_key", False)
            if (
                name not in PROVIDER_NAMES
                or not isinstance(base_url, str)
                or not isinstance(model, str)
                or len(model) > 200
                or (api_key is not None and not isinstance(api_key, str))
                or (api_key is not None and len(api_key) > 2048)
                or (api_key is not None and any(char in api_key for char in "\x00\r\n"))
                or not isinstance(clear_api_key, bool)
                or name in normalized
            ):
                raise ValueError("Provider settings have an invalid format.")
            if patient_model is None:
                patient_model = self._patient_models[name]
            if evaluator_model is None:
                evaluator_model = self._evaluator_models[name]
            if (
                not isinstance(patient_model, str)
                or not isinstance(evaluator_model, str)
                or len(patient_model) > 200
                or len(evaluator_model) > 200
                or any(char in patient_model for char in "\x00\r\n")
                or any(char in evaluator_model for char in "\x00\r\n")
            ):
                raise ValueError("Provider settings have an invalid format.")
            normalized[name] = (
                validate_provider_url(base_url),
                model.strip(),
                patient_model.strip(),
                evaluator_model.strip(),
                api_key,
                clear_api_key,
            )

        if set(normalized) != set(PROVIDER_NAMES):
            raise ValueError("Settings for all providers are required.")

        with self._lock:
            saved: dict[str, dict[str, str]] = {}
            next_keys: dict[ProviderName, str] = {}
            next_patient_models: dict[ProviderName, str] = {}
            next_evaluator_models: dict[ProviderName, str] = {}
            for name in PROVIDER_NAMES:
                (
                    base_url,
                    model,
                    patient_model,
                    evaluator_model,
                    api_key,
                    clear_api_key,
                ) = normalized[name]
                current_key = self.settings.get_provider(name).api_key
                if clear_api_key:
                    next_key = ""
                elif api_key is not None:
                    next_key = api_key
                elif self._saved_api_keys is not None:
                    # Preserve the last user-saved value, not an environment
                    # override that was loaded into runtime Settings.
                    next_key = self._saved_api_keys[name]
                else:
                    env_key = os.environ.get(
                        f"{PROVIDER_DEFAULTS[name][1]}_API_KEY"
                    )
                    next_key = (
                        ""
                        if env_key is not None and current_key == env_key
                        else current_key
                    )
                next_keys[name] = next_key
                entry = {
                    "base_url": base_url,
                    "model": model,
                    "patient_model": patient_model,
                    "evaluator_model": evaluator_model,
                }
                if next_key:
                    entry["api_key_protected"] = protect_provider_key(next_key)
                saved[name] = entry

                next_patient_models[name] = patient_model
                next_evaluator_models[name] = evaluator_model

            self._write(
                {
                    "active_provider": active_provider,
                    "local_only": (
                        self.settings.local_only_mode
                        if local_only is None
                        else local_only
                    ),
                    "providers": saved,
                }
            )
            self._saved_api_keys = next_keys
            self._patient_models = next_patient_models
            self._evaluator_models = next_evaluator_models

            for name in PROVIDER_NAMES:
                entry = saved[name]
                env_key_name = f"{PROVIDER_DEFAULTS[name][1]}_API_KEY"
                self.settings.update_provider(
                    name,
                    base_url=entry["base_url"],
                    model=entry["model"],
                    api_key=os.environ.get(
                        env_key_name,
                        next_keys[name],
                    ),
                )
            self.settings.llm_provider = active_provider
            if local_only is not None:
                self.settings.local_only_mode = local_only

    def model_for_role(
        self,
        role: str,
        provider: ProviderName | None = None,
    ) -> str:
        """Return a role override, or the provider's general model fallback."""

        provider_name = provider or self.settings.llm_provider
        if role == "patient":
            selected = self._patient_models[provider_name]
        elif role == "evaluator":
            selected = self._evaluator_models[provider_name]
        else:
            raise ValueError("Model role must be patient or evaluator.")
        return selected or self.settings.get_provider(provider_name).model

    def _write(self, data: dict[str, object]) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                json.dump(data, output, ensure_ascii=False, indent=2)
                output.write("\n")
            if os.name != "nt":
                temporary_path.chmod(0o600)
            temporary_path.replace(path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise OSError("Provider settings could not be saved.") from exc
