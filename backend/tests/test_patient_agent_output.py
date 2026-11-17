import pytest
from pydantic import ValidationError

from app.llm.patient_agent_output import (
    MAX_PATIENT_RESPONSE_LENGTH,
    PATIENT_AGENT_OUTPUT_SCHEMA_ID,
    PATIENT_AGENT_OUTPUT_SCHEMA_VERSION,
    PatientAgentOutput,
    PatientAgentOutputError,
    parse_patient_agent_output,
)


def test_valid_persian_output_is_parsed():
    result = parse_patient_agent_output(
        '{"content":"سلام، امروز کمی مضطرب هستم."}'
    )

    assert isinstance(result, PatientAgentOutput)
    assert result.content == "سلام، امروز کمی مضطرب هستم."



def test_standard_json_markdown_fence_is_accepted():
    result = parse_patient_agent_output(
        '```json\n{"content":"سلام، امروز کمی مضطرب هستم."}\n```'
    )
    assert result.content == "سلام، امروز کمی مضطرب هستم."


def test_standard_json_fence_with_outer_whitespace_is_accepted():
    result = parse_patient_agent_output(
        '\n  ```json\n{"content":"Hello"}\n```  \n'
    )
    assert result.content == "Hello"


@pytest.mark.parametrize(
    "raw_output",
    [
        'Here is the response:\n```json\n{"content":"Hello"}\n```',
        '```python\n{"content":"Hello"}\n```',
        '```json\n{"content":"Hello"}\n```\n```',
    ],
)
def test_unsupported_markdown_wrappers_are_rejected(raw_output):
    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


def test_output_schema_has_explicit_version():
    assert PATIENT_AGENT_OUTPUT_SCHEMA_ID == "PATIENT_AGENT_OUTPUT_V0.1"
    assert PATIENT_AGENT_OUTPUT_SCHEMA_VERSION == "0.1"


def test_output_contains_only_content():
    result = parse_patient_agent_output(
        '{"content":"I feel anxious."}'
    )

    assert result.model_dump() == {
        "content": "I feel anxious.",
    }


@pytest.mark.parametrize(
    "raw_output",
    [
        "",
        "not-json",
        '{"content":',
        '["not", "an object"]',
        '"just a string"',
        "null",
    ],
)
def test_invalid_json_or_non_object_output_is_rejected(raw_output):
    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


@pytest.mark.parametrize(
    "raw_output",
    [
        '{"content":""}',
        '{"content":"   "}',
        '{"content":"\\n\\t  "}',
    ],
)
def test_empty_or_whitespace_content_is_rejected(raw_output):
    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


def test_extra_operational_fields_are_rejected():
    raw_output = (
        '{"content":"Hello",'
        '"session_id":"session-001",'
        '"role":"patient",'
        '"response_status":"completed"}'
    )

    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


def test_model_cannot_supply_message_metadata():
    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(
            '{"content":"Hello","message_id":"message-001"}'
        )


@pytest.mark.parametrize(
    "raw_output",
    [
        '{"content":123}',
        '{"content":null}',
        '{"content":["not", "a", "string"]}',
        '{"content":true}',
    ],
)
def test_non_string_content_is_rejected(raw_output):
    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


def test_response_length_limit_is_enforced():
    content = "x" * (MAX_PATIENT_RESPONSE_LENGTH + 1)
    raw_output = '{"content":"' + content + '"}'

    with pytest.raises(PatientAgentOutputError):
        parse_patient_agent_output(raw_output)


def test_response_at_maximum_length_is_accepted():
    content = "x" * MAX_PATIENT_RESPONSE_LENGTH
    raw_output = '{"content":"' + content + '"}'

    result = parse_patient_agent_output(raw_output)

    assert len(result.content) == MAX_PATIENT_RESPONSE_LENGTH


def test_null_character_is_rejected():
    with pytest.raises(ValidationError):
        PatientAgentOutput(content="Hello\x00World")


def test_parsed_output_is_immutable():
    result = parse_patient_agent_output(
        '{"content":"Hello"}'
    )

    with pytest.raises(ValidationError):
        result.content = "Modified"


def test_parser_rejects_non_string_input():
    with pytest.raises(TypeError):
        parse_patient_agent_output({"content": "Hello"})
