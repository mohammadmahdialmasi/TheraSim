
import pytest
from pydantic import ValidationError

from app.services.character_model import (
    AttachmentDimensions,
    BigFiveProfile,
    CharacterPersonalityProfile,
    CharacterStateTransitionProposal,
    CharacterStateValues,
    CognitiveSchemaTheme,
    MemoryEvidenceQuote,
    MemoryProposal,
    PersonalityEstimate,
    ValueHypothesis,
)


def estimate(level="unknown", source_refs=()):
    return PersonalityEstimate(
        level=level,
        confidence="low",
        context_scope="not sufficiently established",
        rationale="No broad trait inference is made without adequate evidence.",
        source_refs=source_refs,
    )


def profile():
    unknown = estimate()
    return CharacterPersonalityProfile(
        personality_profile_id="personality-ava-001-v1",
        character_id="AVA-001",
        case_id="case-ava-001",
        case_version_id="case-ava-001-v1",
        theory_bundle_version="0.1",
        big_five=BigFiveProfile(
            openness=unknown,
            conscientiousness=unknown,
            extraversion=unknown,
            agreeableness=unknown,
            neuroticism=unknown,
        ),
        attachment=AttachmentDimensions(
            anxiety=unknown,
            avoidance=unknown,
        ),
        interpersonal={
            "agency": unknown,
            "communion": unknown,
        },
    )


def test_profile_accepts_unknown_traits_without_inventing_scores():
    result = profile()

    assert result.character_id == "AVA-001"
    assert result.big_five.extraversion.level == "unknown"
    assert result.attachment.anxiety.level == "unknown"


def test_profile_is_immutable():
    result = profile()

    with pytest.raises(ValidationError):
        result.character_id = "OTHER"


def test_schema_theme_cannot_be_endorsed_without_evidence():
    with pytest.raises(ValidationError):
        CognitiveSchemaTheme(
            theme_id="SCHEMA-001",
            description="Competence-related belief",
            belief_content="I must never make a mistake.",
            status="character_endorsed",
        )


def test_value_hypothesis_requires_evidence_when_endorsed():
    with pytest.raises(ValidationError):
        ValueHypothesis(
            domain="professional growth",
            personal_meaning="Contributing useful ideas",
            status="endorsed",
        )


def test_dynamic_character_state_rejects_out_of_range_values():
    with pytest.raises(ValidationError):
        CharacterStateValues(
            affect_valence=0,
            arousal=5,
            perceived_safety=2,
            social_evaluative_threat=2,
            engagement=2,
            interpersonal_withdrawal=1,
        )


def test_dynamic_character_state_accepts_valid_values():
    result = CharacterStateValues(
        affect_valence=-1,
        arousal=3,
        perceived_safety=2,
        social_evaluative_threat=4,
        engagement=1,
        interpersonal_withdrawal=3,
    )

    assert result.social_evaluative_threat == 4
    assert result.affect_valence == -1


def test_state_transition_requires_evidence():
    with pytest.raises(ValidationError):
        CharacterStateTransitionProposal(
            proposal_id="proposal-1",
            run_id="run-1",
            session_id="session-1",
            variable_name="perceived_safety",
            previous_value=2,
            proposed_value=1,
            evidence_message_ids=(),
            rationale="The interaction may have reduced perceived safety.",
            confidence=0.7,
        )


def test_state_transition_rejects_unknown_variable():
    with pytest.raises(ValidationError):
        CharacterStateTransitionProposal(
            proposal_id="proposal-1",
            run_id="run-1",
            session_id="session-1",
            variable_name="personality_openness",
            previous_value=2,
            proposed_value=1,
            evidence_message_ids=("message-1",),
            rationale="Unsupported state variable.",
            confidence=0.7,
        )


def test_memory_proposal_requires_evidence():
    with pytest.raises(ValidationError):
        MemoryProposal(
            proposal_id="memory-proposal-1",
            memory_type="explicit_disclosure",
            information_class="explicit_disclosure",
            content="The character described a relevant experience.",
            evidence=(),
            confidence=0.9,
        )


def test_memory_proposal_preserves_exact_source_reference():
    result = MemoryProposal(
        proposal_id="memory-proposal-1",
        memory_type="explicit_disclosure",
        information_class="explicit_disclosure",
        content="I felt embarrassed when I was interrupted.",
        evidence=(
            MemoryEvidenceQuote(
                message_id="message-10",
                exact_quote="I felt embarrassed when I was interrupted.",
            ),
        ),
        confidence=0.95,
    )

    assert result.evidence[0].message_id == "message-10"
    assert result.status == "candidate"


def test_memory_proposal_rejects_duplicate_evidence_message_ids():
    with pytest.raises(ValidationError):
        MemoryProposal(
            proposal_id="memory-proposal-1",
            memory_type="reported_outcome",
            information_class="reported_outcome",
            content="A reported outcome.",
            evidence=(
                MemoryEvidenceQuote(
                    message_id="message-10",
                    exact_quote="First quote.",
                ),
                MemoryEvidenceQuote(
                    message_id="message-10",
                    exact_quote="Second quote.",
                ),
            ),
            confidence=0.8,
        )
