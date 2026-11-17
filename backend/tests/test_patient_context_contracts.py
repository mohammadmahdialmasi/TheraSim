import json
from dataclasses import replace

import pytest

from app.llm.patient_context_serializer import patient_context_to_payload
from app.services.patient_context import (
    FrozenJSONObject,
    PatientCaseFact,
    CharacterPersonalityContext,
    PatientCharacterState,
    PatientCharacterStateVariable,
    PatientContext,
    PatientIdentity,
    PatientMemoryItem,
    PatientState,
    PatientStateVariable,
    PatientTranscriptMessage,
    RestrictedProfileContext,
    STATE_VARIABLES,
    freeze_json_object,
    parse_json_array,
    parse_json_object,
    thaw_json,
)


def make_state():
    return PatientState(
        snapshot_id="snapshot-001",
        state_schema_version="1",
        values=tuple(
            PatientStateVariable(name=name, value=1)
            for name in sorted(STATE_VARIABLES)
        ),
    )


def make_profile():
    empty = FrozenJSONObject(())
    return RestrictedProfileContext(
        clinical_formulation=empty,
        relevant_personal_history=empty,
        maintaining_factors=(),
        avoidance_patterns=(),
        hypothesized_functions=empty,
        initial_safety_baseline=empty,
        patient_simulation_instructions=None,
    )


def make_message(
    message_id,
    sequence_number,
    *,
    session_id="session-001",
    session_number=1,
    role="therapist",
):
    return PatientTranscriptMessage(
        message_id=message_id,
        session_id=session_id,
        session_number=session_number,
        sequence_number=sequence_number,
        role=role,
        content="Test message",
        created_at="2026-11-16T10:00:00Z",
    )


def make_context(recent_transcript=()):
    therapist_message = make_message("current-message", 2)

    return PatientContext(
        case_id="case-001",
        case_version_id="version-001",
        run_id="run-001",
        session_id="session-001",
        session_number=1,
        language="fa",
        modality="ACT",
        public_identity=PatientIdentity(
            display_name="Ava",
            age=29,
            occupation="Designer",
            presenting_concerns=("Anxiety",),
            initial_disclosure="I feel anxious in meetings.",
        ),
        restricted_profile=make_profile(),
        relevant_case_facts=(),
        current_state=make_state(),
        longitudinal_memory=(),
        recent_transcript=recent_transcript,
        therapist_message=therapist_message,
    )


def test_json_freezing_is_deep_and_independent_of_source():
    source = {
        "nested": {
            "items": [1, {"active": True}],
        }
    }

    frozen = freeze_json_object(source, "payload")
    source["nested"]["items"].append(99)

    assert thaw_json(frozen) == {
        "nested": {
            "items": [1, {"active": True}],
        }
    }


def test_frozen_json_object_rejects_mutable_nested_values():
    with pytest.raises(TypeError):
        FrozenJSONObject((("items", ["mutable"]),))


def test_frozen_json_object_rejects_mutable_nested_dictionaries():
    with pytest.raises(TypeError):
        FrozenJSONObject((("nested", {"value": 1}),))


def test_json_object_parser_rejects_non_object_roots():
    with pytest.raises(ValueError):
        parse_json_object('["not", "an object"]', "payload")


def test_json_object_parser_rejects_non_finite_numbers():
    with pytest.raises(ValueError):
        parse_json_object('{"value": NaN}', "payload")


def test_json_array_parser_requires_an_array():
    with pytest.raises(ValueError):
        parse_json_array('{"value": 1}', "payload")


def test_patient_state_rejects_invalid_member_types_cleanly():
    with pytest.raises(TypeError):
        PatientState(
            snapshot_id="snapshot-001",
            state_schema_version="1",
            values=("invalid",),
        )


def test_patient_state_requires_all_six_variables():
    with pytest.raises(ValueError):
        PatientState(
            snapshot_id="snapshot-001",
            state_schema_version="1",
            values=(
                PatientStateVariable(
                    name="therapeutic_alliance",
                    value=2,
                ),
            ),
        )


def test_case_fact_rejects_confirmed_hypothesis():
    with pytest.raises(ValueError):
        PatientCaseFact(
            case_fact_id="fact-001",
            fact_category="history",
            information_class="case_hypothesis",
            content="A hypothetical pattern.",
            disclosure_policy="contextually_disclosable",
            disclosure_status="confirmed_disclosed",
            relevance_metadata=None,
        )


def test_case_fact_rejects_candidate_under_restricted_policy():
    with pytest.raises(ValueError):
        PatientCaseFact(
            case_fact_id="fact-001",
            fact_category="history",
            information_class="established_fact",
            content="A restricted fact.",
            disclosure_policy="restricted",
            disclosure_status="candidate_disclosed",
            relevance_metadata=None,
        )


def test_patient_memory_rejects_therapist_hypothesis():
    with pytest.raises(ValueError):
        PatientMemoryItem(
            memory_id="memory-001",
            source_session_id="session-001",
            memory_type="interpretation",
            information_class="therapist_hypothesis",
            content="Therapist hypothesis.",
            source_message_ids=("message-001",),
            confidence=0.8,
            memory_version=1,
        )


def test_patient_memory_requires_transcript_evidence():
    with pytest.raises(ValueError):
        PatientMemoryItem(
            memory_id="memory-001",
            source_session_id="session-001",
            memory_type="disclosed_fact",
            information_class="explicit_disclosure",
            content="A disclosed fact.",
            source_message_ids=(),
            confidence=0.9,
            memory_version=1,
        )


def test_context_rejects_invalid_case_fact_member_type():
    with pytest.raises(TypeError):
        context = make_context()
        PatientContext(
            case_id=context.case_id,
            case_version_id=context.case_version_id,
            run_id=context.run_id,
            session_id=context.session_id,
            session_number=context.session_number,
            language=context.language,
            modality=context.modality,
            public_identity=context.public_identity,
            restricted_profile=context.restricted_profile,
            relevant_case_facts=("invalid",),
            current_state=context.current_state,
            longitudinal_memory=(),
            recent_transcript=(),
            therapist_message=context.therapist_message,
        )


def test_context_rejects_invalid_transcript_member_type():
    with pytest.raises(TypeError):
        make_context(recent_transcript=("invalid",))


def test_context_rejects_out_of_order_transcript():
    first = make_message("message-001", 1)
    second = make_message("message-002", 2)

    with pytest.raises(ValueError):
        make_context(recent_transcript=(second, first))


def test_context_rejects_current_message_duplicated_in_history():
    current = make_message("current-message", 1)

    with pytest.raises(ValueError):
        make_context(recent_transcript=(current,))


def test_patient_context_supports_session_numbers_above_three():
    context = make_context()
    session_id = "session-4"
    therapist_message = replace(
        context.therapist_message,
        session_id=session_id,
        session_number=4,
    )

    updated = replace(
        context,
        session_id=session_id,
        session_number=4,
        therapist_message=therapist_message,
    )

    assert updated.session_number == 4
    assert make_message(
        "history-session-4",
        1,
        session_id=session_id,
        session_number=4,
    ).session_number == 4


def test_context_rejects_history_after_current_therapist_message():
    later = make_message("message-later", 3)

    with pytest.raises(ValueError):
        make_context(recent_transcript=(later,))

def test_patient_context_serializer_uses_explicit_field_allowlists():
    context = make_context(
        recent_transcript=(
            make_message(
                "history-message",
                1,
                role="patient",
            ),
        )
    )

    payload = patient_context_to_payload(context)

    assert set(payload) == {
        "context_schema_version",
        "language",
        "modality",
        "public_identity",
        "disclosed_case_facts",
        "longitudinal_disclosures",
        "recent_transcript",
        "therapist_message",
    }
    assert payload["context_schema_version"] == "2.0"

    assert set(payload["public_identity"]) == {
        "display_name",
        "age",
        "occupation",
        "presenting_concerns",
        "initial_disclosure",
    }

    assert set(payload["recent_transcript"][0]) == {
        "role",
        "content",
    }

    assert payload["therapist_message"]["role"] == "therapist"
    assert payload["recent_transcript"] == [{
        "role": "patient",
        "content": "Test message",
    }]


def test_patient_context_serializer_preserves_nested_authorized_data():
    history_message = make_message(
        "history-message",
        1,
        role="patient",
    )

    empty = FrozenJSONObject(())

    profile = RestrictedProfileContext(
        clinical_formulation=freeze_json_object(
            {
                "core": "private formulation sentinel",
                "nested": {
                    "indicators": ["avoidance", "self-criticism"],
                },
            },
            "clinical_formulation",
        ),
        relevant_personal_history=freeze_json_object(
            {"background": "fictional history"},
            "relevant_personal_history",
        ),
        maintaining_factors=(
            freeze_json_object(
                {"factor": "short-term relief"},
                "maintaining_factor",
            ),
        ),
        avoidance_patterns=("avoids speaking in meetings",),
        hypothesized_functions=freeze_json_object(
            {"function": "private hypothesis sentinel"},
            "hypothesized_functions",
        ),
        initial_safety_baseline=empty,
        patient_simulation_instructions="Respond naturally in Persian.",
    )

    fact = PatientCaseFact(
        case_fact_id="fact-001",
        fact_category="personal_history",
        information_class="established_fact",
        content="A fictional established fact.",
        disclosure_policy="contextually_disclosable",
        disclosure_status="confirmed_disclosed",
        relevance_metadata=freeze_json_object(
            {"source": "case_definition"},
            "relevance_metadata",
        ),
    )
    pending_fact = PatientCaseFact(
        case_fact_id="fact-pending",
        fact_category="personal_history",
        information_class="established_fact",
        content="Pending disclosure sentinel.",
        disclosure_policy="contextually_disclosable",
        disclosure_status="candidate_disclosed",
        relevance_metadata=None,
    )
    initial_fact = PatientCaseFact(
        case_fact_id="fact-initial",
        fact_category="presenting_concern",
        information_class="established_fact",
        content="An initially authorized fact.",
        disclosure_policy="initial_disclosure",
        disclosure_status="not_disclosed",
        relevance_metadata=None,
    )

    memory = PatientMemoryItem(
        memory_id="memory-001",
        source_session_id="session-001",
        memory_type="disclosed_fact",
        information_class="explicit_disclosure",
        content="The client previously described an uncomfortable meeting.",
        source_message_ids=("history-message",),
        confidence=0.95,
        memory_version=1,
    )

    context = make_context(
        recent_transcript=(history_message,)
    )

    context = replace(
        context,
        restricted_profile=profile,
        relevant_case_facts=(fact, pending_fact, initial_fact),
        longitudinal_memory=(memory,),
    )

    payload = patient_context_to_payload(context)

    assert payload["disclosed_case_facts"] == [
        {
            "fact_category": "personal_history",
            "content": "A fictional established fact.",
        },
        {
            "fact_category": "presenting_concern",
            "content": "An initially authorized fact.",
        },
    ]
    assert payload["longitudinal_disclosures"] == [{
        "content": "The client previously described an uncomfortable meeting.",
    }]
    serialized_payload = json.dumps(payload)
    assert "private formulation sentinel" not in serialized_payload
    assert "private hypothesis sentinel" not in serialized_payload
    assert "Pending disclosure sentinel" not in serialized_payload


def test_patient_context_serializer_produces_json_safe_persian_payload():
    context = make_context()
    payload = patient_context_to_payload(context)

    payload["therapist_message"]["content"] = "سلام، امروز چه احساسی دارید؟"

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
    )

    decoded = json.loads(encoded)

    assert "سلام" in encoded
    assert decoded["therapist_message"]["content"] == (
        "سلام، امروز چه احساسی دارید؟"
    )


def test_patient_context_serializer_returns_independent_json_values():
    context = make_context()
    first_payload = patient_context_to_payload(context)

    first_payload["public_identity"]["presenting_concerns"].append(
        "externally modified"
    )

    second_payload = patient_context_to_payload(context)

    assert second_payload["public_identity"]["presenting_concerns"] == [
        "Anxiety"
    ]


def test_patient_context_serializer_rejects_untyped_input():
    with pytest.raises(TypeError):
        patient_context_to_payload({"case_id": "case-001"})

def test_character_personality_and_dynamic_state_are_separate_from_act_state():
    personality = CharacterPersonalityContext(
        configured=True,
        profile_version=2,
        profile_data=freeze_json_object(
            {
                "communication_style": ["careful", "measured"],
                "big_five": {
                    "extraversion": {
                        "level": "low",
                        "confidence": "moderate",
                    }
                },
            },
            "profile_data",
        ),
    )

    character_state = PatientCharacterState(
        snapshot_id="character-snapshot-001",
        state_schema_version="0.1",
        values=tuple(
            PatientCharacterStateVariable(name=name, value=value)
            for name, value in {
                "affect_valence": -1,
                "arousal": 3,
                "perceived_safety": 2,
                "social_evaluative_threat": 4,
                "engagement": 1,
                "interpersonal_withdrawal": 3,
            }.items()
        ),
    )

    context = replace(
        make_context(),
        character_personality=personality,
        character_state=character_state,
    )

    payload = patient_context_to_payload(context)

    assert "character_personality" not in payload
    assert "character_state" not in payload
    assert "current_state" not in payload


def test_character_state_rejects_out_of_range_valence():
    with pytest.raises(ValueError):
        PatientCharacterStateVariable(
            name="affect_valence",
            value=3,
        )


def test_character_personality_unconfigured_state_cannot_contain_data():
    with pytest.raises(ValueError):
        CharacterPersonalityContext(
            configured=False,
            profile_version=None,
            profile_data=freeze_json_object(
                {"communication_style": ["invented"]},
                "profile_data",
            ),
        )


def test_memory_scope_is_validated():
    memory = PatientMemoryItem(
        memory_id="memory-episodic",
        source_session_id="session-001",
        memory_type="event",
        information_class="explicit_disclosure",
        content="A previously disclosed experience.",
        source_message_ids=("history-message",),
        confidence=0.9,
        memory_version=1,
        memory_scope="episodic",
    )

    assert memory.memory_scope == "episodic"

    with pytest.raises(ValueError):
        replace(memory, memory_scope="unsupported")
