from dataclasses import dataclass, field
from ipaddress import ip_address
from os import environ
from typing import Literal, Mapping, cast
from urllib.parse import urlsplit, urlunsplit


ProviderName = Literal["ollama", "lm_studio", "llama_cpp", "custom"]
PROVIDER_NAMES: tuple[ProviderName, ...] = (
    "ollama",
    "lm_studio",
    "llama_cpp",
    "custom",
)

PROVIDER_DEFAULTS: dict[ProviderName, tuple[str, str]] = {
    "ollama": ("http://127.0.0.1:11434/v1", "OLLAMA"),
    "lm_studio": ("http://127.0.0.1:1234/v1", "LM_STUDIO"),
    "llama_cpp": ("http://127.0.0.1:8080/v1", "LLAMA_CPP"),
    "custom": ("http://127.0.0.1:8000/v1", "CUSTOM_OPENAI"),
}


def _is_loopback_host(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost":
        return True
    try:
        address = ip_address(normalized)
    except ValueError:
        return False
    return address.is_loopback


def provider_url_is_loopback(value: str) -> bool:
    parsed = urlsplit(validate_provider_url(value))
    hostname = parsed.hostname
    return bool(hostname and _is_loopback_host(hostname))


def validate_provider_url(value: str, setting_name: str = "base_url") -> str:
    if not value or value != value.strip():
        raise ValueError(f"{setting_name} must be a valid HTTP(S) URL.")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{setting_name} must be a valid HTTP(S) URL.") from exc

    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{setting_name} must use HTTP(S) without user-info, query, or fragment."
        )

    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"{setting_name} port must be between 1 and 65535.")

    if parsed.scheme.lower() == "http" and not _is_loopback_host(hostname):
        raise ValueError(
            f"{setting_name} must use HTTPS for non-loopback hosts."
        )

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )


def provider_url_origin_for_display(value: str) -> str:
    """Return only a provider URL's origin, excluding credentials and paths."""

    parsed = urlsplit(value)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Provider URL must include a hostname.")

    authority = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port is not None:
        authority = f"{authority}:{parsed.port}"
    return f"{parsed.scheme.lower()}://{authority}"


@dataclass
class ProviderConfig:
    name: ProviderName
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)


@dataclass
class Settings:
    app_name: str
    app_version: str
    llm_provider: ProviderName
    providers: dict[ProviderName, ProviderConfig]
    request_timeout_seconds: float
    local_only_mode: bool

    @classmethod
    def from_environment(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> "Settings":
        source = environ if env is None else env

        provider_value = source.get(
            "THERASIM_LLM_PROVIDER", "ollama"
        ).strip().lower()
        if provider_value not in PROVIDER_NAMES:
            raise ValueError(
                "THERASIM_LLM_PROVIDER must be ollama, lm_studio, "
                "llama_cpp, or custom."
            )

        try:
            timeout = float(source.get("THERASIM_LLM_TIMEOUT", "120"))
        except ValueError as exc:
            raise ValueError(
                "THERASIM_LLM_TIMEOUT must be numeric."
            ) from exc
        if not 1 <= timeout <= 600:
            raise ValueError(
                "THERASIM_LLM_TIMEOUT must be between 1 and 600."
            )

        local_only_value = source.get("THERASIM_LOCAL_ONLY", "true").strip().lower()
        if local_only_value in {"1", "true", "yes", "on"}:
            local_only_mode = True
        elif local_only_value in {"0", "false", "no", "off"}:
            local_only_mode = False
        else:
            raise ValueError("THERASIM_LOCAL_ONLY must be a boolean value.")

        providers: dict[ProviderName, ProviderConfig] = {}
        for name in PROVIDER_NAMES:
            default_url, prefix = PROVIDER_DEFAULTS[name]
            url_key = f"{prefix}_BASE_URL"
            model_key = f"{prefix}_MODEL"
            api_key_key = f"{prefix}_API_KEY"
            providers[name] = ProviderConfig(
                name=name,
                base_url=validate_provider_url(
                    source.get(url_key, default_url), url_key
                ),
                model=source.get(model_key, "").strip(),
                api_key=source.get(api_key_key, ""),
            )

        # Preserve the historical Ollama/LM Studio environment variable names.
        providers["custom"].base_url = validate_provider_url(
            source.get(
                "CUSTOM_OPENAI_BASE_URL",
                providers["custom"].base_url,
            ),
            "CUSTOM_OPENAI_BASE_URL",
        )

        return cls(
            app_name="TheraSim API",
            app_version="0.3.1",
            llm_provider=cast(ProviderName, provider_value),
            providers=providers,
            request_timeout_seconds=timeout,
            local_only_mode=local_only_mode,
        )

    def get_provider(
        self,
        name: ProviderName | None = None,
    ) -> ProviderConfig:
        return self.providers[name or self.llm_provider]

    @property
    def active_provider(self) -> ProviderConfig:
        return self.get_provider()

    def update_provider(
        self,
        name: ProviderName,
        *,
        base_url: str,
        model: str,
        api_key: str,
    ) -> ProviderConfig:
        config = self.providers[name]
        config.base_url = validate_provider_url(base_url)
        config.model = model.strip()
        config.api_key = api_key
        return config


settings = Settings.from_environment()
