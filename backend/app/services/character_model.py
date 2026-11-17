
"""Versioned domain contracts for character-centered simulation.

These contracts validate proposed and authored data. They do not persist
records or authorize model-generated state changes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


CHARACTER_PERSONALITY_SCHEMA_VERSION = "0.1"
CHARACTER_STATE_SCHEMA_VERSION = "0.1"
CHARACTER_DYNAMICS_PROPOSAL_SCHEMA_VERSION = "0.1"

PersonalityLevel = Literal[
    "very_low",
    "low",
    "mid_low",
    "mid",
    "mid_high",
    "high",
    "very_high",
    "unknown",
]

ConfidenceLevel = Literal["low", "moderate", "high"]

ProfileAuthoringStatus = Literal[
    "draft",
    "reviewed",
    "active",
    "retired",
]

SourceStatus = Literal[
    "hypothesis",
    "under_exploration",
    "character_endorsed",
    "not_endorsed",
    "revised",
]

ValueStatus = Literal[
    "candidate",
    "explored",
    "endorsed",
    "not_endorsed",
    "revised",
]

CHARACTER_STATE_BOUNDS = {
    "affect_valence": (-2, 2),
    "arousal": (0, 4),
    "perceived_safety": (0, 4),
    "social_evaluative_threat": (0, 4),
    "engagement": (0, 4),
    "interpersonal_withdrawal": (0, 4),
}


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )


class PersonalityEstimate(StrictFrozenModel):
    """An authored, uncertain trait estimate, not a psychometric score."""

    level: PersonalityLevel = "unknown"
    confidence: ConfidenceLevel = "low"
    context_scope: StrictStr
    rationale: StrictStr
    source_refs: tuple[StrictStr, ...] = ()

    @field_validator("context_scope", "rationale")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Personality estimate text must not be blank.")
        return value

    @field_validator("source_refs")
    @classmethod
    def validate_source_refs(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("Source references must not be blank.")
        if len(value) != len(set(value)):
            raise ValueError("Source references must be unique.")
        return value


class BigFiveProfile(StrictFrozenModel):
    openness: PersonalityEstimate
    conscientiousness: PersonalityEstimate
    extraversion: PersonalityEstimate
    agreeableness: PersonalityEstimate
    neuroticism: PersonalityEstimate


class AttachmentDimensions(StrictFrozenModel):
    """Dimensional attachment tendencies, not categorical diagnoses."""

    anxiety: PersonalityEstimate
    avoidance: PersonalityEstimate


class InterpersonalDimensions(StrictFrozenModel):
    """Interpersonal circumplex coordinates."""

    agency: PersonalityEstimate
    communion: PersonalityEstimate


class CognitiveSchemaTheme(StrictFrozenModel):
    theme_id: StrictStr
    description: StrictStr
    belief_content: StrictStr
    status: SourceStatus = "hypothesis"
    confidence: ConfidenceLevel = "low"
    source_refs: tuple[StrictStr, ...] = ()

    @field_validator("theme_id", "description", "belief_content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Schema-theme text must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_endorsement_evidence(self):
        if self.status in {"character_endorsed", "revised"}:
            if not self.source_refs:
                raise ValueError(
                    "Character-endorsed schema themes require source evidence."
                )
        return self


class EmotionRegulationPattern(StrictFrozenModel):
    pattern_id: StrictStr
    description: StrictStr
    relevant_contexts: tuple[StrictStr, ...]
    short_term_function: StrictStr
    possible_long_term_costs: tuple[StrictStr, ...] = ()
    source_refs: tuple[StrictStr, ...] = ()

    @field_validator(
        "pattern_id",
        "description",
        "short_term_function",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Emotion-regulation text must not be blank.")
        return value


class ValueHypothesis(StrictFrozenModel):
    domain: StrictStr
    personal_meaning: StrictStr
    status: ValueStatus = "candidate"
    confidence: ConfidenceLevel = "low"
    source_refs: tuple[StrictStr, ...] = ()

    @field_validator("domain", "personal_meaning")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value-hypothesis text must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_endorsed_value_evidence(self):
        if self.status in {"endorsed", "revised"} and not self.source_refs:
            raise ValueError(
                "Endorsed or revised values require source evidence."
            )
        return self


class CharacterPersonalityProfile(StrictFrozenModel):
    """Immutable authored personality definition for one case version."""

    personality_profile_id: StrictStr
    character_id: StrictStr
    case_id: StrictStr
    case_version_id: StrictStr
    personality_schema_version: StrictStr = (
        CHARACTER_PERSONALITY_SCHEMA_VERSION
    )
    theory_bundle_version: StrictStr
    profile_version: StrictInt = Field(default=1, ge=1)
    authoring_status: ProfileAuthoringStatus = "draft"

    # Theory modules are independently selectable; an absent module is unknown,
    # not a request to infer a trait from unrelated case details.
    big_five: BigFiveProfile | None = None
    attachment: AttachmentDimensions | None = None
    interpersonal: InterpersonalDimensions | None = None

    schema_themes: tuple[CognitiveSchemaTheme, ...] = ()
    emotion_regulation_patterns: tuple[EmotionRegulationPattern, ...] = ()
    value_hypotheses: tuple[ValueHypothesis, ...] = ()
    initial_state: dict[str, StrictInt] | None = None
    communication_style: tuple[StrictStr, ...] = ()
    authoring_notes: tuple[StrictStr, ...] = ()

    @field_validator(
        "personality_profile_id",
        "character_id",
        "case_id",
        "case_version_id",
        "personality_schema_version",
        "theory_bundle_version",
    )
    @classmethod
    def validate_identity_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Character profile identity must not be blank.")
        return value

    @model_validator(mode="after")
    def validate_nested_identity(self):
        if self.initial_state is not None:
            CharacterStateValues.model_validate(self.initial_state)

        theme_ids = [item.theme_id for item in self.schema_themes]
        if len(theme_ids) != len(set(theme_ids)):
            raise ValueError("Schema theme identifiers must be unique.")

        pattern_ids = [
            item.pattern_id for item in self.emotion_regulation_patterns
        ]
        if len(pattern_ids) != len(set(pattern_ids)):
            raise ValueError(
                "Emotion-regulation pattern identifiers must be unique."
            )

        return self


class CharacterStateValues(StrictFrozenModel):
    """Generic dynamic state; deliberately separate from ACT process state."""

    affect_valence: StrictInt
    arousal: StrictInt
    perceived_safety: StrictInt
    social_evaluative_threat: StrictInt
    engagement: StrictInt
    interpersonal_withdrawal: StrictInt

    @model_validator(mode="after")
    def validate_state_bounds(self):
        for name, (minimum, maximum) in CHARACTER_STATE_BOUNDS.items():
            value = getattr(self, name)
            if not minimum <= value <= maximum:
                raise ValueError(
                    f"{name} must be between {minimum} and {maximum}."
                )
        return self


class CharacterStateSnapshot(StrictFrozenModel):
    snapshot_id: StrictStr
    run_id: StrictStr
    state_schema_version: StrictStr = CHARACTER_STATE_SCHEMA_VERSION
    session_id: StrictStr | None = None
    previous_snapshot_id: StrictStr | None = None
    snapshot_reason: StrictStr
    values: CharacterStateValues

    @field_validator(
        "snapshot_id",
        "run_id",
        "state_schema_version",
        "snapshot_reason",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Character-state identity must not be blank.")
        return value


class CharacterStateTransitionProposal(StrictFrozenModel):
    """Untrusted proposal. It cannot authorize or persist a transition."""

    proposal_id: StrictStr
    run_id: StrictStr
    session_id: StrictStr
    variable_name: StrictStr
    previous_value: StrictInt
    proposed_value: StrictInt
    evidence_message_ids: tuple[StrictStr, ...]
    rationale: StrictStr
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    status: Literal["candidate", "requires_review"] = "candidate"

    @model_validator(mode="after")
    def validate_transition(self):
        bounds = CHARACTER_STATE_BOUNDS.get(self.variable_name)
        if bounds is None:
            raise ValueError("Unknown character-state variable.")

        minimum, maximum = bounds
        if not minimum <= self.previous_value <= maximum:
            raise ValueError("Previous state value is out of bounds.")
        if not minimum <= self.proposed_value <= maximum:
            raise ValueError("Proposed state value is out of bounds.")

        if not self.evidence_message_ids:
            raise ValueError("State proposals require message evidence.")

        if any(not item.strip() for item in self.evidence_message_ids):
            raise ValueError("Evidence message identifiers must not be blank.")

        if len(self.evidence_message_ids) != len(
            set(self.evidence_message_ids)
        ):
            raise ValueError("Evidence message identifiers must be unique.")

        if not self.rationale.strip():
            raise ValueError("Transition rationale must not be blank.")

        return self


class MemoryEvidenceQuote(StrictFrozenModel):
    """A proposed exact excerpt; backend must verify it against the message."""

    message_id: StrictStr
    exact_quote: StrictStr

    @field_validator("message_id", "exact_quote")
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Memory evidence text must not be blank.")
        return value


class MemoryProposal(StrictFrozenModel):
    """Candidate memory requiring application-side evidence validation."""

    proposal_id: StrictStr
    memory_type: StrictStr
    information_class: Literal[
        "confirmed_fact",
        "explicit_disclosure",
        "system_generated_summary",
        "reported_outcome",
    ]
    content: StrictStr
    evidence: tuple[MemoryEvidenceQuote, ...]
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    status: Literal["candidate", "requires_review"] = "candidate"

    @model_validator(mode="after")
    def validate_memory_evidence(self):
        if not self.proposal_id.strip():
            raise ValueError("Memory proposal identifier must not be blank.")

        if not self.memory_type.strip() or not self.content.strip():
            raise ValueError("Memory type and content must not be blank.")

        if not self.evidence:
            raise ValueError("Memory proposals require source evidence.")

        message_ids = [item.message_id for item in self.evidence]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("Memory evidence message IDs must be unique.")

        return self


class CharacterEventProposal(StrictFrozenModel):
    """Candidate event that must be checked against persisted source messages."""

    proposal_id: StrictStr
    event_type: StrictStr
    actor: Literal["therapist", "patient", "context", "system"]
    summary: StrictStr
    evidence: tuple[MemoryEvidenceQuote, ...]
    status: Literal["candidate", "requires_review"] = "candidate"

    @model_validator(mode="after")
    def validate_event_evidence(self):
        if not self.proposal_id.strip():
            raise ValueError("Event proposal identifier must not be blank.")

        if not self.event_type.strip() or not self.summary.strip():
            raise ValueError("Event type and summary must not be blank.")

        if not self.evidence:
            raise ValueError("Event proposals require source evidence.")

        return self


class CharacterDynamicsProposal(StrictFrozenModel):
    """Structured candidate output for a future orchestrator extraction step."""

    proposal_schema_version: StrictStr = (
        CHARACTER_DYNAMICS_PROPOSAL_SCHEMA_VERSION
    )
    events: tuple[CharacterEventProposal, ...] = ()
    memories: tuple[MemoryProposal, ...] = ()
    state_transitions: tuple[CharacterStateTransitionProposal, ...] = ()
