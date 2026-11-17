"""Versioned and strictly validated Patient Agent output contract."""

import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)


PATIENT_AGENT_OUTPUT_SCHEMA_ID = "PATIENT_AGENT_OUTPUT_V0.1"
PATIENT_AGENT_OUTPUT_SCHEMA_VERSION = "0.1"
MAX_PATIENT_RESPONSE_LENGTH = 12_000


class PatientAgentOutputError(ValueError):
    """The generated Patient Agent output violates its output contract."""


class PatientAgentOutput(BaseModel):
    """Untrusted model output accepted only after strict validation.

    The model may generate conversational content only.
    All operational identifiers and message metadata are backend-owned.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    content: StrictStr = Field(
        min_length=1,
        max_length=MAX_PATIENT_RESPONSE_LENGTH,
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Patient response must not be whitespace only.")

        if "\x00" in value:
            raise ValueError("Patient response must not contain null characters.")

        return value


def _normalize_json_output(raw_output: str) -> str:
    """Accept plain JSON or one exclusive standard JSON Markdown fence."""

    candidate = raw_output.strip()
    if not candidate.startswith("```"):
        return candidate

    match = re.fullmatch(
        r"```json[ \t]*\r?\n(?P<body>.*?)\r?\n```[ \t]*",
        candidate,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise PatientAgentOutputError(
            "Patient Agent output contains an unsupported Markdown wrapper."
        )

    return match.group("body").strip()


def parse_patient_agent_output(
    raw_output: str,
) -> PatientAgentOutput:
    """Parse and validate the model's raw JSON response.

    Validation errors intentionally do not expose raw generated content
    through the public exception message.
    """

    if not isinstance(raw_output, str):
        raise TypeError("raw_output must be a string.")

    try:
        normalized_output = _normalize_json_output(raw_output)
        return PatientAgentOutput.model_validate_json(normalized_output)
    except ValidationError:
        raise PatientAgentOutputError(
            "Patient Agent output does not match the required schema."
        ) from None
