"""Patient Agent orchestration over an injected local model client."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from typing import Any, Protocol

from app.core.config import ProviderConfig, ProviderName
from app.llm.patient_agent_output import (
    PATIENT_AGENT_OUTPUT_SCHEMA_ID,
    PATIENT_AGENT_OUTPUT_SCHEMA_VERSION,
    PatientAgentOutput,
    PatientAgentOutputError,
    parse_patient_agent_output,
)
from app.llm.patient_agent_prompt import (
    PATIENT_AGENT_PROMPT_ID,
    PATIENT_AGENT_PROMPT_VERSION,
    PATIENT_AGENT_SYSTEM_PROMPT,
)
from app.llm.patient_context_serializer import patient_context_to_payload
from app.services.patient_context import PatientContext


DEFAULT_PATIENT_AGENT_TEMPERATURE = 0.7
DEFAULT_PATIENT_AGENT_MAX_TOKENS = 1024


class ChatCompletionClient(Protocol):
    """Minimal provider interface required by the Patient Agent."""

    config: ProviderConfig

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        ...


class PatientAgentError(RuntimeError):
    """Base error for Patient Agent execution failures."""


class PatientAgentIncompleteResponseError(PatientAgentError):
    """The model stopped before completing its response."""


class PatientAgentOutputValidationError(PatientAgentError):
    """The model returned output that violates the Patient Agent contract."""


@dataclass(frozen=True, slots=True)
class PatientAgentResult:
    """Validated patient response and non-clinical execution metadata."""

    output: PatientAgentOutput
    provider: ProviderName
    model_identifier: str
    prompt_id: str
    prompt_version: str
    input_schema_version: str
    output_schema_id: str
    output_schema_version: str
    temperature: float
    max_tokens: int
    finish_reason: str | None
    usage: tuple[tuple[str, int], ...] | None


class PatientAgent:
    """Generate and validate one synthetic client's conversational reply.

    The agent has no database or repository dependency. It receives an
    already authorized PatientContext and delegates inference to an
    injected OpenAI-compatible client.
    """

    def __init__(
        self,
        client: ChatCompletionClient,
        model: str | None = None,
        *,
        temperature: float = DEFAULT_PATIENT_AGENT_TEMPERATURE,
        max_tokens: int = DEFAULT_PATIENT_AGENT_MAX_TOKENS,
    ) -> None:
        if not isinstance(client.config, ProviderConfig):
            raise TypeError("client.config must be a ProviderConfig.")

        selected_model = model if model is not None else client.config.model

        if not isinstance(selected_model, str) or not selected_model.strip():
            raise ValueError("A non-empty Patient Agent model is required.")

        if (
            isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature)
            or not 0 <= temperature <= 2
        ):
            raise ValueError("temperature must be a finite number from 0 to 2.")

        if (
            isinstance(max_tokens, bool)
            or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 32768
        ):
            raise ValueError("max_tokens must be an integer from 1 to 32768.")

        self.client = client
        self.model = selected_model.strip()
        self.temperature = float(temperature)
        self.max_tokens = max_tokens

    @staticmethod
    def _build_messages(
        context: PatientContext,
    ) -> list[dict[str, str]]:
        payload = patient_context_to_payload(context)

        user_content = json.dumps(
            {"patient_context": payload},
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

        return [
            {
                "role": "system",
                "content": PATIENT_AGENT_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

    @staticmethod
    def _normalize_usage(value: object) -> tuple[tuple[str, int], ...] | None:
        if not isinstance(value, Mapping):
            return None

        allowed_fields = (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )

        normalized = []

        for field in allowed_fields:
            item = value.get(field)

            if (
                isinstance(item, int)
                and not isinstance(item, bool)
                and item >= 0
            ):
                normalized.append((field, item))

        return tuple(normalized) if normalized else None

    def generate_response(
        self,
        context: PatientContext,
    ) -> PatientAgentResult:
        """Generate one response from the exact authorized context."""

        if not isinstance(context, PatientContext):
            raise TypeError("context must be a PatientContext instance.")

        messages = self._build_messages(context)

        # The model call occurs without any database transaction managed
        # by this component. The caller owns persistence and lifecycle.
        response = self.client.chat(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        if not isinstance(response, Mapping):
            raise PatientAgentOutputValidationError(
                "Provider returned an invalid completion envelope."
            )

        finish_reason = response.get("finish_reason")

        if finish_reason is not None and not isinstance(finish_reason, str):
            raise PatientAgentOutputValidationError(
                "Provider returned an invalid finish reason."
            )

        if finish_reason == "length":
            raise PatientAgentIncompleteResponseError(
                "Patient Agent generation reached the output token limit."
            )

        raw_output = response.get("content")

        if not isinstance(raw_output, str):
            raise PatientAgentOutputValidationError(
                "Provider completion does not contain text content."
            )

        try:
            output = parse_patient_agent_output(raw_output)
        except PatientAgentOutputError:
            raise PatientAgentOutputValidationError(
                "Patient Agent returned an invalid structured response."
            ) from None

        reported_model = response.get("model", self.model)

        if not isinstance(reported_model, str) or not reported_model.strip():
            reported_model = self.model

        return PatientAgentResult(
            output=output,
            provider=self.client.config.name,
            model_identifier=reported_model.strip(),
            prompt_id=PATIENT_AGENT_PROMPT_ID,
            prompt_version=PATIENT_AGENT_PROMPT_VERSION,
            input_schema_version=context.context_schema_version,
            output_schema_id=PATIENT_AGENT_OUTPUT_SCHEMA_ID,
            output_schema_version=PATIENT_AGENT_OUTPUT_SCHEMA_VERSION,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            finish_reason=finish_reason,
            usage=self._normalize_usage(response.get("usage")),
        )
