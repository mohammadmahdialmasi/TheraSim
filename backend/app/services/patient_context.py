"""Immutable data contracts for authorized Patient Agent context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from typing import TypeAlias


PATIENT_CONTEXT_SCHEMA_VERSION = "1.1"

INFORMATION_CLASSES = frozenset({
    "established_fact",
    "case_hypothesis",
    "unspecified_information",
})

DISCLOSURE_POLICIES = frozenset({
    "initial_disclosure",
    "contextually_disclosable",
    "restricted",
    "not_applicable",
})

DISCLOSURE_STATUSES = frozenset({
    "not_disclosed",
    "candidate_disclosed",
    "confirmed_disclosed",
    "requires_review",
})

PATIENT_MEMORY_INFORMATION_CLASSES = frozenset({
    "confirmed_fact",
    "explicit_disclosure",
    "system_generated_summary",
    "reported_outcome",
})

STATE_VARIABLES = frozenset({
    "therapeutic_alliance",
    "disclosure_readiness",
    "experiential_avoidance",
    "willingness",
    "values_clarity",
    "committed_action_readiness",
})

CHARACTER_STATE_VARIABLE_BOUNDS = {
    "affect_valence": (-2, 2),
    "arousal": (0, 4),
    "perceived_safety": (0, 4),
    "social_evaluative_threat": (0, 4),
    "engagement": (0, 4),
    "interpersonal_withdrawal": (0, 4),
}

CHARACTER_STATE_VARIABLES = frozenset(
    CHARACTER_STATE_VARIABLE_BOUNDS
)

MEMORY_SCOPES = frozenset({
    "legacy_unclassified",
    "episodic",
    "semantic",
    "therapeutic",
})


JSONScalar: TypeAlias = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class FrozenJSONObject:
    """Immutable representation of a JSON object."""

    entries: tuple[tuple[str, FrozenJSONValue], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise TypeError("JSON object entries must be a tuple.")

        keys = []

        for entry in self.entries:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("Every JSON object entry must be a key-value pair.")

            key, _ = entry

            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings.")

            keys.append(key)

        if len(keys) != len(set(keys)):
            raise ValueError("JSON object keys must be unique.")

        for _, item in self.entries:
            if not _is_frozen_json_value(item):
                raise TypeError(
                    "FrozenJSONObject values must be deeply immutable JSON values."
                )


FrozenJSONValue: TypeAlias = (
    JSONScalar
    | tuple["FrozenJSONValue", ...]
    | FrozenJSONObject
)


def _is_frozen_json_value(value: object) -> bool:
    """Return whether a value is recursively immutable and JSON-compatible."""

    if value is None or isinstance(value, (str, bool, int)):
        return True

    if isinstance(value, float):
        return isfinite(value)

    if isinstance(value, FrozenJSONObject):
        return True

    if isinstance(value, tuple):
        return all(_is_frozen_json_value(item) for item in value)

    return False


def _freeze_json_value(value: object, field_name: str) -> FrozenJSONValue:
    """Recursively convert JSON-compatible data into immutable values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite number.")
        return value

    if isinstance(value, dict):
        keys = list(value)

        if not all(isinstance(key, str) for key in keys):
            raise ValueError(f"{field_name} contains a non-string key.")

        entries = []

        for key in sorted(keys):
            entries.append(
                (key, _freeze_json_value(value[key], field_name))
            )

        return FrozenJSONObject(tuple(entries))

    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json_value(item, field_name)
            for item in value
        )

    raise ValueError(
        f"{field_name} contains a value that is not JSON-compatible."
    )


def freeze_json_object(
    value: object,
    field_name: str,
) -> FrozenJSONObject:
    """Validate and freeze a JSON object."""

    if isinstance(value, FrozenJSONObject):
        return value

    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object.")

    frozen = _freeze_json_value(value, field_name)

    if not isinstance(frozen, FrozenJSONObject):
        raise ValueError(f"{field_name} must be a JSON object.")

    return frozen


def parse_json_object(
    raw_value: str | None,
    field_name: str,
) -> FrozenJSONObject:
    """Parse a database JSON object without permissive fallback behavior."""

    if raw_value is None:
        return FrozenJSONObject(())

    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must contain JSON text.")

    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"{field_name} contains invalid JSON.") from exc

    return freeze_json_object(parsed, field_name)


def parse_json_array(
    raw_value: str | None,
    field_name: str,
) -> tuple[FrozenJSONValue, ...]:
    """Parse a database JSON array into an immutable tuple."""

    if raw_value is None:
        return ()

    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must contain JSON text.")

    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"{field_name} contains invalid JSON.") from exc

    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must contain a JSON array.")

    frozen = _freeze_json_value(parsed, field_name)

    if not isinstance(frozen, tuple):
        raise ValueError(f"{field_name} must contain a JSON array.")

    return frozen


def thaw_json(value: FrozenJSONValue) -> object:
    """Convert immutable JSON values into ordinary JSON-compatible values."""

    if isinstance(value, FrozenJSONObject):
        return {
            key: thaw_json(item)
            for key, item in value.entries
        }

    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]

    return value


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")


@dataclass(frozen=True, slots=True)
class PatientIdentity:
    """Public identity information authorized for Patient Agent context."""

    display_name: str
    age: int | None
    occupation: str | None
    presenting_concerns: tuple[str, ...]
    initial_disclosure: str | None

    def __post_init__(self) -> None:
        _require_text(self.display_name, "display_name")

        if self.age is not None:
            if (
                isinstance(self.age, bool)
                or not isinstance(self.age, int)
                or self.age <= 0
            ):
                raise ValueError("age must be a positive integer or None.")

        if self.occupation is not None and not isinstance(
            self.occupation, str
        ):
            raise ValueError("occupation must be a string or None.")

        if not isinstance(self.presenting_concerns, tuple):
            raise TypeError("presenting_concerns must be a tuple.")

        if not all(
            isinstance(item, str) and item.strip()
            for item in self.presenting_concerns
        ):
            raise ValueError("Presenting concerns must be non-empty strings.")

        if self.initial_disclosure is not None and not isinstance(
            self.initial_disclosure, str
        ):
            raise ValueError("initial_disclosure must be a string or None.")


@dataclass(frozen=True, slots=True)
class RestrictedProfileContext:
    """Restricted fictional case context for the Patient Agent only."""

    clinical_formulation: FrozenJSONObject
    relevant_personal_history: FrozenJSONObject
    maintaining_factors: tuple[FrozenJSONValue, ...]
    avoidance_patterns: tuple[FrozenJSONValue, ...]
    hypothesized_functions: FrozenJSONObject
    initial_safety_baseline: FrozenJSONObject
    patient_simulation_instructions: str | None

    def __post_init__(self) -> None:
        for name in (
            "clinical_formulation",
            "relevant_personal_history",
            "hypothesized_functions",
            "initial_safety_baseline",
        ):
            if not isinstance(getattr(self, name), FrozenJSONObject):
                raise TypeError(f"{name} must be a FrozenJSONObject.")

        for name in ("maintaining_factors", "avoidance_patterns"):
            if not isinstance(getattr(self, name), tuple):
                raise TypeError(f"{name} must be a tuple.")

        if self.patient_simulation_instructions is not None:
            if not isinstance(self.patient_simulation_instructions, str):
                raise ValueError(
                    "patient_simulation_instructions must be a string or None."
                )


@dataclass(frozen=True, slots=True)
class PatientCaseFact:
    """One restricted case fact with its disclosure metadata."""

    case_fact_id: str
    fact_category: str
    information_class: str
    content: str
    disclosure_policy: str
    disclosure_status: str
    relevance_metadata: FrozenJSONObject | None

    def __post_init__(self) -> None:
        for name in (
            "case_fact_id",
            "fact_category",
            "content",
        ):
            _require_text(getattr(self, name), name)

        if self.information_class not in INFORMATION_CLASSES:
            raise ValueError("Invalid case-fact information_class.")

        if self.disclosure_policy not in DISCLOSURE_POLICIES:
            raise ValueError("Invalid case-fact disclosure_policy.")

        if self.disclosure_status not in DISCLOSURE_STATUSES:
            raise ValueError("Invalid case-fact disclosure_status.")

        if self.disclosure_status in {
            "candidate_disclosed",
            "confirmed_disclosed",
        } and self.disclosure_policy not in {
            "initial_disclosure",
            "contextually_disclosable",
        }:
            raise ValueError(
                "This disclosure policy does not permit a disclosure candidate."
            )

        if (
            self.disclosure_status == "confirmed_disclosed"
            and self.information_class != "established_fact"
        ):
            raise ValueError(
                "Only established facts may be confirmed as disclosed."
            )

        if self.relevance_metadata is not None:
            if not isinstance(self.relevance_metadata, FrozenJSONObject):
                raise TypeError(
                    "relevance_metadata must be a FrozenJSONObject or None."
                )


@dataclass(frozen=True, slots=True)
class PatientStateVariable:
    """One validated simulation-state value."""

    name: str
    value: int

    def __post_init__(self) -> None:
        if self.name not in STATE_VARIABLES:
            raise ValueError(f"Unknown state variable: {self.name}.")

        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, int)
            or not 0 <= self.value <= 4
        ):
            raise ValueError(
                f"State variable {self.name} must be an integer from 0 to 4."
            )


@dataclass(frozen=True, slots=True)
class PatientState:
    """Current canonical state snapshot supplied to the Patient Agent."""

    snapshot_id: str
    state_schema_version: str
    values: tuple[PatientStateVariable, ...]

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.state_schema_version, "state_schema_version")

        if not isinstance(self.values, tuple):
            raise TypeError("State values must be a tuple.")

        if not all(
            isinstance(item, PatientStateVariable)
            for item in self.values
        ):
            raise TypeError("Invalid PatientState variable item.")

        names = [item.name for item in self.values]

        if len(names) != len(set(names)):
            raise ValueError("State variables must be unique.")

        if set(names) != STATE_VARIABLES:
            raise ValueError(
                "The PatientState must contain every required state variable."
            )


@dataclass(frozen=True, slots=True)
class PatientCharacterStateVariable:
    """One transient character-state value, separate from ACT process state."""

    name: str
    value: int

    def __post_init__(self) -> None:
        bounds = CHARACTER_STATE_VARIABLE_BOUNDS.get(self.name)

        if bounds is None:
            raise ValueError("Unknown character-state variable.")

        minimum, maximum = bounds

        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, int)
            or not minimum <= self.value <= maximum
        ):
            raise ValueError(
                f"Character-state variable {self.name} is out of bounds."
            )


@dataclass(frozen=True, slots=True)
class PatientCharacterState:
    """Current run-specific transient character state."""

    snapshot_id: str
    state_schema_version: str
    values: tuple[PatientCharacterStateVariable, ...]

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "character_state.snapshot_id")
        _require_text(
            self.state_schema_version,
            "character_state.state_schema_version",
        )

        if not isinstance(self.values, tuple):
            raise TypeError("Character-state values must be a tuple.")

        if not all(
            isinstance(item, PatientCharacterStateVariable)
            for item in self.values
        ):
            raise TypeError("Invalid character-state variable item.")

        names = [item.name for item in self.values]

        if len(names) != len(set(names)):
            raise ValueError("Character-state variables must be unique.")

        if set(names) != CHARACTER_STATE_VARIABLES:
            raise ValueError(
                "Character state must contain all six required variables."
            )


@dataclass(frozen=True, slots=True)
class CharacterPersonalityContext:
    """Curated stable personality information for the Patient Agent."""

    configured: bool
    profile_version: int | None
    profile_data: FrozenJSONObject

    def __post_init__(self) -> None:
        if not isinstance(self.configured, bool):
            raise TypeError("configured must be a boolean.")

        if not isinstance(self.profile_data, FrozenJSONObject):
            raise TypeError("profile_data must be a FrozenJSONObject.")

        if self.configured:
            if (
                isinstance(self.profile_version, bool)
                or not isinstance(self.profile_version, int)
                or self.profile_version < 1
            ):
                raise ValueError(
                    "Configured personality requires a positive profile version."
                )

            if not self.profile_data.entries:
                raise ValueError(
                    "Configured personality requires authored profile data."
                )
        elif self.profile_version is not None or self.profile_data.entries:
            raise ValueError(
                "Unconfigured personality cannot contain profile data."
            )


@dataclass(frozen=True, slots=True)
class PatientMemoryItem:
    """A source-linked memory item authorized for patient continuity."""

    memory_id: str
    source_session_id: str | None
    memory_type: str
    information_class: str
    content: str
    source_message_ids: tuple[str, ...]
    confidence: float | None
    memory_version: int
    memory_scope: str = "legacy_unclassified"

    def __post_init__(self) -> None:
        _require_text(self.memory_id, "memory_id")
        _require_text(self.memory_type, "memory_type")
        _require_text(self.content, "content")

        if self.memory_scope not in MEMORY_SCOPES:
            raise ValueError("Invalid memory scope.")

        if self.source_session_id is not None:
            _require_text(self.source_session_id, "source_session_id")

        if self.information_class not in PATIENT_MEMORY_INFORMATION_CLASSES:
            raise ValueError(
                "This memory information_class is not permitted "
                "in PatientContext."
            )

        if not isinstance(self.source_message_ids, tuple):
            raise TypeError("source_message_ids must be a tuple.")

        if not self.source_message_ids:
            raise ValueError("Memory items require transcript evidence.")

        if not all(
            isinstance(item, str) and item.strip()
            for item in self.source_message_ids
        ):
            raise ValueError("Memory evidence identifiers must be non-empty.")

        if len(self.source_message_ids) != len(set(self.source_message_ids)):
            raise ValueError("Memory evidence identifiers must be unique.")

        if self.confidence is not None:
            if (
                isinstance(self.confidence, bool)
                or not isinstance(self.confidence, (int, float))
                or not 0.0 <= self.confidence <= 1.0
            ):
                raise ValueError("Memory confidence must be between 0 and 1.")

        if (
            isinstance(self.memory_version, bool)
            or not isinstance(self.memory_version, int)
            or self.memory_version < 1
        ):
            raise ValueError("memory_version must be a positive integer.")


@dataclass(frozen=True, slots=True)
class PatientTranscriptMessage:
    """A historical or current therapist/patient transcript message."""

    message_id: str
    session_id: str
    session_number: int
    sequence_number: int
    role: str
    content: str
    created_at: str

    def __post_init__(self) -> None:
        for name in (
            "message_id",
            "session_id",
            "content",
            "created_at",
        ):
            _require_text(getattr(self, name), name)

        if self.role not in {"therapist", "patient"}:
            raise ValueError("Invalid transcript message role.")

        if (
            isinstance(self.session_number, bool)
            or not isinstance(self.session_number, int)
            or self.session_number < 1
        ):
            raise ValueError("session_number must be positive.")

        if (
            isinstance(self.sequence_number, bool)
            or not isinstance(self.sequence_number, int)
            or self.sequence_number < 1
        ):
            raise ValueError("sequence_number must be positive.")


@dataclass(frozen=True, slots=True)
class PatientContext:
    """The complete authorized context passed to the Patient Agent."""

    case_id: str
    case_version_id: str
    run_id: str
    session_id: str
    session_number: int
    language: str
    modality: str

    public_identity: PatientIdentity
    restricted_profile: RestrictedProfileContext
    relevant_case_facts: tuple[PatientCaseFact, ...]
    current_state: PatientState
    longitudinal_memory: tuple[PatientMemoryItem, ...]
    recent_transcript: tuple[PatientTranscriptMessage, ...]
    therapist_message: PatientTranscriptMessage

    # Optional only for compatibility with older manually constructed contexts.
    # PatientContextService always supplies both fields for persisted runs.
    character_personality: CharacterPersonalityContext | None = None
    character_state: PatientCharacterState | None = None

    context_schema_version: str = PATIENT_CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "case_version_id",
            "run_id",
            "session_id",
            "language",
            "modality",
            "context_schema_version",
        ):
            _require_text(getattr(self, name), name)

        if (
            isinstance(self.session_number, bool)
            or not isinstance(self.session_number, int)
            or self.session_number < 1
        ):
            raise ValueError("session_number must be positive.")

        if not isinstance(self.public_identity, PatientIdentity):
            raise TypeError("public_identity must be PatientIdentity.")

        if not isinstance(self.restricted_profile, RestrictedProfileContext):
            raise TypeError("restricted_profile must be RestrictedProfileContext.")

        if not isinstance(self.current_state, PatientState):
            raise TypeError("current_state must be PatientState.")

        if (
            self.character_personality is not None
            and not isinstance(
                self.character_personality,
                CharacterPersonalityContext,
            )
        ):
            raise TypeError(
                "character_personality must be CharacterPersonalityContext or None."
            )

        if (
            self.character_state is not None
            and not isinstance(self.character_state, PatientCharacterState)
        ):
            raise TypeError(
                "character_state must be PatientCharacterState or None."
            )

        if not isinstance(self.therapist_message, PatientTranscriptMessage):
            raise TypeError("therapist_message must be a transcript message.")

        if self.therapist_message.role != "therapist":
            raise ValueError("therapist_message must have the therapist role.")

        if self.therapist_message.session_id != self.session_id:
            raise ValueError("therapist_message belongs to another session.")

        if self.therapist_message.session_number != self.session_number:
            raise ValueError("therapist_message has an invalid session number.")

        for name in (
            "relevant_case_facts",
            "longitudinal_memory",
            "recent_transcript",
        ):
            if not isinstance(getattr(self, name), tuple):
                raise TypeError(f"{name} must be a tuple.")

        if not all(
            isinstance(item, PatientCaseFact)
            for item in self.relevant_case_facts
        ):
            raise TypeError("Invalid PatientCaseFact item.")

        if not all(
            isinstance(item, PatientMemoryItem)
            for item in self.longitudinal_memory
        ):
            raise TypeError("Invalid PatientMemoryItem item.")

        if not all(
            isinstance(item, PatientTranscriptMessage)
            for item in self.recent_transcript
        ):
            raise TypeError("Invalid recent transcript message.")

        fact_ids = [item.case_fact_id for item in self.relevant_case_facts]

        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("Case-fact identifiers must be unique.")

        memory_ids = [item.memory_id for item in self.longitudinal_memory]

        if len(memory_ids) != len(set(memory_ids)):
            raise ValueError("Memory identifiers must be unique.")

        message_ids = [item.message_id for item in self.recent_transcript]

        if len(message_ids) != len(set(message_ids)):
            raise ValueError("Transcript message identifiers must be unique.")

        if self.therapist_message.message_id in message_ids:
            raise ValueError(
                "The current therapist message must not be duplicated "
                "in recent_transcript."
            )

        positions = tuple(
            (message.session_number, message.sequence_number)
            for message in self.recent_transcript
        )

        if positions != tuple(sorted(positions)):
            raise ValueError(
                "Recent transcript messages must be in chronological order."
            )

        if len(positions) != len(set(positions)):
            raise ValueError(
                "Transcript sequence positions must be unique."
            )

        for message in self.recent_transcript:
            if message.session_number > self.session_number:
                raise ValueError(
                    "Recent transcript contains a message from a future session."
                )

            if message.session_number == self.session_number:
                if message.session_id != self.session_id:
                    raise ValueError(
                        "Current-session transcript messages must belong "
                        "to the requested session."
                    )

                if (
                    message.sequence_number
                    >= self.therapist_message.sequence_number
                ):
                    raise ValueError(
                        "Recent transcript contains a message that is not "
                        "earlier than the current therapist message."
                    )

            elif message.session_id == self.session_id:
                raise ValueError(
                    "A message from an earlier session has the current "
                    "session identifier."
                )
