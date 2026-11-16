from dataclasses import dataclass
from os import environ
from typing import Literal, Mapping, cast


ProviderName = Literal["ollama", "lm_studio"]


@dataclass(frozen=True)
class ProviderConfig:
    name: ProviderName
    base_url: str
    model: str
    api_key: str


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    llm_provider: ProviderName

    ollama_base_url: str
    ollama_model: str
    ollama_api_key: str

    lm_studio_base_url: str
    lm_studio_model: str
    lm_studio_api_key: str

    request_timeout_seconds: float

    @classmethod
    def from_environment(
        cls,
        env: Mapping[str, str] | None = None,
    ) -> "Settings":
        source = environ if env is None else env

        provider_value = source.get(
            "THERASIM_LLM_PROVIDER", "ollama"
        ).strip().lower()

        if provider_value not in ("ollama", "lm_studio"):
            raise ValueError(
                "THERASIM_LLM_PROVIDER must be "
                "'ollama' or 'lm_studio'."
            )

        try:
            timeout = float(
                source.get("THERASIM_LLM_TIMEOUT", "120")
            )
        except ValueError as exc:
            raise ValueError(
                "THERASIM_LLM_TIMEOUT must be numeric."
            ) from exc

        if not 1 <= timeout <= 600:
            raise ValueError(
                "THERASIM_LLM_TIMEOUT must be between 1 and 600."
            )

        return cls(
            app_name="TheraSim API",
            app_version="0.1.0",
            llm_provider=cast(ProviderName, provider_value),

            ollama_base_url=source.get(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ).rstrip("/"),
            ollama_model=source.get("OLLAMA_MODEL", "").strip(),
            ollama_api_key=source.get("OLLAMA_API_KEY", "ollama"),

            lm_studio_base_url=source.get(
                "LM_STUDIO_BASE_URL",
                "http://127.0.0.1:1234/v1",
            ).rstrip("/"),
            lm_studio_model=source.get(
                "LM_STUDIO_MODEL", ""
            ).strip(),
            lm_studio_api_key=source.get(
                "LM_STUDIO_API_KEY", ""
            ),

            request_timeout_seconds=timeout,
        )

    def get_provider(
        self,
        name: ProviderName | None = None,
    ) -> ProviderConfig:
        selected = name or self.llm_provider

        if selected == "ollama":
            return ProviderConfig(
                name="ollama",
                base_url=self.ollama_base_url,
                model=self.ollama_model,
                api_key=self.ollama_api_key,
            )

        return ProviderConfig(
            name="lm_studio",
            base_url=self.lm_studio_base_url,
            model=self.lm_studio_model,
            api_key=self.lm_studio_api_key,
        )

    @property
    def active_provider(self) -> ProviderConfig:
        return self.get_provider()


settings = Settings.from_environment()