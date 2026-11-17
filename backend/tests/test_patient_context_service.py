import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.state import StateRepository, STATE_VARIABLES
from app.services.cases import CaseService
from app.services.disclosures import DisclosureService
from app.services.patient_context_service import (
    PatientContextDataIntegrityError,
    PatientContextMessageNotFoundError,
    PatientContextRunNotActiveError,
    PatientContextSessionNotActiveError,
    PatientContextService,
    PatientContextStateIntegrityError,
    PatientContextTurnConflictError,
)
from app.services.runs import RunService


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "patient-context-service")
    manager.initialize()

    cases = CaseService(manager)

    cases.create_case(
        case_id="case-1",
        case_code="CASE-001",
        display_name="Ava",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )

    cases.create_case_version(
        case_version_id="version-1",
        case_id="case-1",
        version_number="1.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )

    cases.create_public_profile(
        case_version_id="version-1",
        age=29,
        occupation="Designer",
        presenting_concerns=("Anxiety", "Work stress"),
        initial_disclosure="I feel anxious in meetings.",
        created_at=NOW,
    )

    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        repository.create_profile(
            restricted_profile_id="restricted-1",
            case_id="case-1",
            case_version_id="version-1",
            clinical_formulation={
                "primary": "performance anxiety",
                "confidence": "hypothesis",
            },
            relevant_personal_history={
                "work_context": "design team",
            },
            maintaining_factors=("avoidance", "self-criticism"),
            avoidance_patterns=("silence in meetings",),
            hypothesized_functions={
                "avoidance": "short-term reduction in discomfort",
            },
            initial_safety_baseline={
                "acute_risk": "not_indicated_in_synthetic_case",
            },
            patient_simulation_instructions="Respond naturally and consistently.",
            created_at=NOW,
        )

        facts = (
            (
                "FACT-INITIAL",
                "established_fact",
                "initial_disclosure",
                "A known initial disclosure.",
            ),
            (
                "FACT-RESTRICTED",
                "established_fact",
                "restricted",
                "A restricted fictional fact.",
            ),
            (
                "FACT-HYPOTHESIS",
                "case_hypothesis",
                "contextually_disclosable",
                "A hypothetical formulation.",
            ),
        )

        for fact_id, information_class, policy, content in facts:
            repository.create_fact(
                case_id="case-1",
                case_version_id="version-1",
                case_fact_id=fact_id,
                fact_category="test_category",
                information_class=information_class,
                content=content,
                disclosure_policy=policy,
                relevance_metadata={"source": "synthetic-test"},
                created_at=NOW,
            )

    runs = RunService(manager)

    runs.create_run(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    runs.start_run("run-1", started_at=NOW)

    with manager.transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        StateRepository(connection).create_snapshot(
            snapshot_id="snapshot-1",
            run_id="run-1",
            state_schema_version="1",
            snapshot_reason="initial",
            created_at=NOW,
            values={
                "therapeutic_alliance": 2,
                "disclosure_readiness": 1,
                "experiential_avoidance": 4,
                "willingness": 1,
                "values_clarity": 2,
                "committed_action_readiness": 1,
            },
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content=(
                "I feel tense when I speak in meetings, and I enjoy gardening "
                "on weekends."
            ),
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-1",
            session_id="session-1",
            sequence_number=2,
            role="therapist",
            content="Can we return to your anxiety in meetings?",
            created_at=NOW,
        )

        memory = MemoryRepository(connection)

        memory.create_memory(
            memory_id="memory-allowed",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="disclosed_experience",
            information_class="explicit_disclosure",
            content="The client reported tension during meetings.",
            confidence=0.95,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        memory.add_evidence(
            "memory-allowed",
            "patient-1",
            "supports",
        )

        memory.create_memory(
            memory_id="memory-hypothesis",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="interpretation",
            information_class="therapist_hypothesis",
            content="A therapist-generated hypothesis.",
            confidence=0.8,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        memory.add_evidence(
            "memory-hypothesis",
            "therapist-1",
            "supports",
        )

        memory.create_memory(
            memory_id="memory-observation",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="structured_observation",
            information_class="structured_observation",
            content="A system-generated observation.",
            confidence=0.7,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

    disclosures = DisclosureService(manager)
    disclosures.initialize_run_disclosures(
        "run-1",
        created_at=NOW,
    )

    return {
        "manager": manager,
        "runs": runs,
        "service": PatientContextService(manager),
        "disclosures": disclosures,
    }


def build(system, *, session_id="session-1", message_id="therapist-1"):
    return system["service"].build_patient_context(
        "run-1",
        session_id,
        message_id,
    )


def test_builds_complete_authorized_patient_context(system):
    context = build(system)

    assert context.case_id == "case-1"
    assert context.case_version_id == "version-1"
    assert context.run_id == "run-1"
    assert context.session_id == "session-1"
    assert context.session_number == 1
    assert context.language == "fa"
    assert context.modality == "ACT"

    assert context.public_identity.display_name == "Ava"
    assert context.public_identity.age == 29
    assert context.public_identity.occupation == "Designer"
    assert context.public_identity.presenting_concerns == (
        "Anxiety",
        "Work stress",
    )

    assert context.restricted_profile.clinical_formulation.entries
    assert context.restricted_profile.patient_simulation_instructions == (
        "Respond naturally and consistently."
    )

    facts = {
        item.case_fact_id: item
        for item in context.relevant_case_facts
    }

    assert set(facts) == {
        "FACT-INITIAL",
        "FACT-RESTRICTED",
        "FACT-HYPOTHESIS",
    }

    assert facts["FACT-RESTRICTED"].disclosure_policy == "restricted"
    assert facts["FACT-RESTRICTED"].disclosure_status == "not_disclosed"
    assert facts["FACT-HYPOTHESIS"].information_class == "case_hypothesis"

    state = {
        item.name: item.value
        for item in context.current_state.values
    }

    assert state == {
        "therapeutic_alliance": 2,
        "disclosure_readiness": 1,
        "experiential_avoidance": 4,
        "willingness": 1,
        "values_clarity": 2,
        "committed_action_readiness": 1,
    }

    assert context.current_state.snapshot_id == "snapshot-1"

    assert [
        item.message_id
        for item in context.recent_transcript
    ] == ["patient-1"]

    assert context.therapist_message.message_id == "therapist-1"
    assert context.therapist_message.content == (
        "Can we return to your anxiety in meetings?"
    )


def test_excludes_therapist_hypotheses_and_structured_observations(system):
    context = build(system)

    memory_ids = {
        item.memory_id
        for item in context.longitudinal_memory
    }

    assert memory_ids == {"memory-allowed"}
    assert "memory-hypothesis" not in memory_ids
    assert "memory-observation" not in memory_ids


def test_memory_retrieval_prioritizes_relevant_content_and_omits_irrelevant_episodes(
    system,
):
    with system["manager"].transaction("operational") as connection:
        memory = MemoryRepository(connection)
        memory.create_memory(
            memory_id="memory-irrelevant",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="disclosed_experience",
            information_class="explicit_disclosure",
            content="The client enjoys gardening on weekends.",
            confidence=0.99,
            memory_version=1,
            memory_scope="episodic",
            created_at=NOW,
            updated_at=NOW,
        )
        memory.add_evidence("memory-irrelevant", "patient-1", "supports")

    context = PatientContextService(
        system["manager"],
        max_memory_items=1,
    ).build_patient_context(
        "run-1",
        "session-1",
        "therapist-1",
    )

    assert [item.memory_id for item in context.longitudinal_memory] == [
        "memory-allowed"
    ]


def test_irrelevant_episodic_memory_is_not_included_in_context(system):
    with system["manager"].transaction("operational") as connection:
        memory = MemoryRepository(connection)
        memory.create_memory(
            memory_id="memory-irrelevant",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="disclosed_experience",
            information_class="explicit_disclosure",
            content="The client enjoys gardening on weekends.",
            confidence=0.9,
            memory_version=1,
            memory_scope="episodic",
            created_at=NOW,
            updated_at=NOW,
        )
        memory.add_evidence("memory-irrelevant", "patient-1", "supports")

    context = build(system)

    assert "memory-irrelevant" not in {
        item.memory_id for item in context.longitudinal_memory
    }


def test_requires_exact_disclosure_record_for_every_case_fact(system):
    manager = system["manager"]

    with manager.transaction("restricted") as connection:
        RestrictedCaseRepository(connection).create_fact(
            case_id="case-1",
            case_version_id="version-1",
            case_fact_id="FACT-WITHOUT-DISCLOSURE",
            fact_category="history",
            information_class="established_fact",
            content="A new fact without a disclosure ledger entry.",
            disclosure_policy="contextually_disclosable",
            created_at=NOW,
        )

    with pytest.raises(PatientContextDataIntegrityError):
        build(system)


def test_rejects_a_patient_message_as_the_current_therapist_turn(system):
    with pytest.raises(PatientContextMessageNotFoundError):
        build(system, message_id="patient-1")


def test_rejects_a_therapist_message_that_is_no_longer_latest(system):
    with system["manager"].transaction("operational") as connection:
        MessageRepository(connection).create_message(
            message_id="patient-2",
            session_id="session-1",
            sequence_number=3,
            role="patient",
            content="A later patient response.",
            created_at=NOW,
        )

    with pytest.raises(PatientContextTurnConflictError):
        build(system)


def test_rejects_an_inactive_run(system):
    system["runs"].interrupt_run(
        "run-1",
        interrupted_at=NOW,
    )

    with pytest.raises(PatientContextRunNotActiveError):
        build(system)


def test_rejects_an_inactive_session(system):
    with system["manager"].transaction("operational") as connection:
        SessionRepository(connection).update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

    with pytest.raises(PatientContextSessionNotActiveError):
        build(system)


def test_rejects_multiple_current_snapshot_heads(system):
    values = {
        "therapeutic_alliance": 2,
        "disclosure_readiness": 1,
        "experiential_avoidance": 4,
        "willingness": 1,
        "values_clarity": 2,
        "committed_action_readiness": 1,
    }

    with system["manager"].transaction("operational") as connection:
        StateRepository(connection).create_snapshot(
            snapshot_id="snapshot-fork",
            run_id="run-1",
            state_schema_version="1",
            snapshot_reason="invalid-fork",
            created_at=NOW,
            values=values,
        )

    with pytest.raises(PatientContextStateIntegrityError):
        build(system)


def test_rejects_an_incomplete_current_state_snapshot(system):
    with system["manager"].transaction("operational") as connection:
        connection.execute(
            """
            DELETE FROM state_snapshot_values
            WHERE snapshot_id = ?
              AND variable_name = ?
            """,
            ("snapshot-1", "willingness"),
        )

    with pytest.raises(PatientContextStateIntegrityError):
        build(system)


def test_rejects_memory_evidence_from_the_current_therapist_turn(system):
    with system["manager"].transaction("operational") as connection:
        memory = MemoryRepository(connection)

        memory.create_memory(
            memory_id="memory-from-current-turn",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="reported_outcome",
            information_class="reported_outcome",
            content="This memory refers to the current therapist message.",
            confidence=0.8,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        memory.add_evidence(
            "memory-from-current-turn",
            "therapist-1",
            "supports",
        )

    with pytest.raises(PatientContextDataIntegrityError):
        build(system)


def test_includes_completed_previous_session_history(system):
    manager = system["manager"]

    with manager.transaction("operational") as connection:
        sessions = SessionRepository(connection)

        sessions.update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

        sessions.create_session(
            session_id="session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-2",
            session_id="session-2",
            sequence_number=1,
            role="patient",
            content="I noticed the same feeling again.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-2",
            session_id="session-2",
            sequence_number=2,
            role="therapist",
            content="What happened next?",
            created_at=NOW,
        )

    context = build(
        system,
        session_id="session-2",
        message_id="therapist-2",
    )

    assert [
        (item.session_number, item.message_id)
        for item in context.recent_transcript
    ] == [
        (1, "patient-1"),
        (1, "therapist-1"),
        (2, "patient-2"),
    ]

    assert context.therapist_message.message_id == "therapist-2"

    memory_ids = {
        item.memory_id
        for item in context.longitudinal_memory
    }

    assert "memory-allowed" in memory_ids


def test_context_construction_does_not_change_operational_state(system):
    manager = system["manager"]

    with manager.connection("operational") as connection:
        before_messages = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

        before_snapshots = connection.execute(
            "SELECT COUNT(*) FROM state_snapshots"
        ).fetchone()[0]

        before_disclosures = connection.execute(
            "SELECT COUNT(*) FROM case_fact_disclosures"
        ).fetchone()[0]

        before_memory = connection.execute(
            "SELECT COUNT(*) FROM memory_items"
        ).fetchone()[0]

    build(system)

    with manager.connection("operational") as connection:
        after_messages = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

        after_snapshots = connection.execute(
            "SELECT COUNT(*) FROM state_snapshots"
        ).fetchone()[0]

        after_disclosures = connection.execute(
            "SELECT COUNT(*) FROM case_fact_disclosures"
        ).fetchone()[0]

        after_memory = connection.execute(
            "SELECT COUNT(*) FROM memory_items"
        ).fetchone()[0]

    assert after_messages == before_messages
    assert after_snapshots == before_snapshots
    assert after_disclosures == before_disclosures
    assert after_memory == before_memory

def test_rejects_state_snapshot_chain_that_moves_back_to_an_earlier_session(system):
    manager = system["manager"]

    values = {
        "therapeutic_alliance": 2,
        "disclosure_readiness": 1,
        "experiential_avoidance": 4,
        "willingness": 1,
        "values_clarity": 2,
        "committed_action_readiness": 1,
    }

    with manager.transaction("operational") as connection:
        sessions = SessionRepository(connection)

        sessions.update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

        sessions.create_session(
            session_id="session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        state = StateRepository(connection)

        state.create_snapshot(
            snapshot_id="snapshot-session-2",
            run_id="run-1",
            session_id="session-2",
            previous_snapshot_id="snapshot-1",
            state_schema_version="1",
            snapshot_reason="session-2-state",
            created_at=NOW,
            values=values,
        )

        state.create_snapshot(
            snapshot_id="snapshot-regressed",
            run_id="run-1",
            session_id="session-1",
            previous_snapshot_id="snapshot-session-2",
            state_schema_version="1",
            snapshot_reason="invalid-session-regression",
            created_at=NOW,
            values=values,
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-2",
            session_id="session-2",
            sequence_number=1,
            role="patient",
            content="I noticed the same feeling again.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-2",
            session_id="session-2",
            sequence_number=2,
            role="therapist",
            content="What happened this time?",
            created_at=NOW,
        )

    with pytest.raises(PatientContextStateIntegrityError):
        build(
            system,
            session_id="session-2",
            message_id="therapist-2",
        )


def test_rejects_explicit_disclosure_memory_without_patient_authored_evidence(system):
    manager = system["manager"]

    with manager.transaction("operational") as connection:
        sessions = SessionRepository(connection)

        sessions.update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

        sessions.create_session(
            session_id="session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-2",
            session_id="session-2",
            sequence_number=1,
            role="patient",
            content="I have been thinking about that conversation.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-2",
            session_id="session-2",
            sequence_number=2,
            role="therapist",
            content="What did you notice?",
            created_at=NOW,
        )

        memory = MemoryRepository(connection)

        memory.create_memory(
            memory_id="memory-invalid-disclosure",
            run_id="run-1",
            source_session_id="session-1",
            memory_type="disclosed_experience",
            information_class="explicit_disclosure",
            content="A purported explicit client disclosure.",
            confidence=0.95,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        memory.add_evidence(
            "memory-invalid-disclosure",
            "therapist-1",
            "supports",
        )

    with pytest.raises(PatientContextDataIntegrityError):
        build(
            system,
            session_id="session-2",
            message_id="therapist-2",
        )



def test_allows_memory_evidence_from_a_prior_session(system):
    manager = system["manager"]

    with manager.transaction("operational") as connection:
        sessions = SessionRepository(connection)

        sessions.update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

        sessions.create_session(
            session_id="session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-2",
            session_id="session-2",
            sequence_number=1,
            role="patient",
            content="I noticed a different response this week.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-2",
            session_id="session-2",
            sequence_number=2,
            role="therapist",
            content="Can you describe that response?",
            created_at=NOW,
        )

        memory = MemoryRepository(connection)

        memory.create_memory(
            memory_id="memory-prior-session-evidence",
            run_id="run-1",
            source_session_id="session-2",
            memory_type="reported_outcome",
            information_class="reported_outcome",
            content="An outcome remembered in the second session.",
            confidence=0.85,
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        memory.add_evidence(
            "memory-prior-session-evidence",
            "patient-1",
            "supports",
        )

    context = build(
        system,
        session_id="session-2",
        message_id="therapist-2",
    )

    assert {
        item.memory_id
        for item in context.longitudinal_memory
    } == {
        "memory-allowed",
        "memory-prior-session-evidence",
    }

def test_loads_run_pinned_personality_and_serializes_memory_scope(system):
    from app.llm.patient_context_serializer import patient_context_to_payload
    from app.services.character_model import CharacterPersonalityProfile
    from app.services.character_personality_service import (
        CharacterPersonalityService,
    )

    profile = CharacterPersonalityProfile(
        personality_profile_id="personality-context-v1",
        character_id="AVA-001",
        case_id="case-1",
        case_version_id="version-1",
        theory_bundle_version="0.1",
        communication_style=("careful", "measured"),
        authoring_notes=("Internal authoring note; never disclose.",),
        initial_state={
            "affect_valence": -1,
            "arousal": 3,
            "perceived_safety": 1,
            "social_evaluative_threat": 4,
            "engagement": 2,
            "interpersonal_withdrawal": 3,
        },
    )

    personality_service = CharacterPersonalityService(system["manager"])
    created_profile = personality_service.create_profile(
        profile,
        created_at=NOW,
    )

    assert created_profile["authoring_status"] == "draft"
    personality_service.review_profile(profile.personality_profile_id)
    personality_service.activate_profile(profile.personality_profile_id)

    run_id = "run-personality-context"
    session_id = "session-personality-context"
    patient_message_id = "patient-personality-context"
    therapist_message_id = "therapist-personality-context"

    system["runs"].create_run(
        run_id=run_id,
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    system["runs"].start_run(run_id, started_at=NOW)

    with system["manager"].transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id=session_id,
            run_id=run_id,
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        StateRepository(connection).create_snapshot(
            snapshot_id="act-snapshot-personality-context",
            run_id=run_id,
            state_schema_version="1",
            snapshot_reason="initial",
            created_at=NOW,
            values={
                "therapeutic_alliance": 2,
                "disclosure_readiness": 1,
                "experiential_avoidance": 4,
                "willingness": 1,
                "values_clarity": 2,
                "committed_action_readiness": 1,
            },
        )

        messages = MessageRepository(connection)
        messages.create_message(
            message_id=patient_message_id,
            session_id=session_id,
            sequence_number=1,
            role="patient",
            content="I feel tense when I speak in meetings.",
            created_at=NOW,
        )
        messages.create_message(
            message_id=therapist_message_id,
            session_id=session_id,
            sequence_number=2,
            role="therapist",
            content="Can we return to anxiety in meetings?",
            created_at=NOW,
        )

        memory = MemoryRepository(connection)
        memory.create_memory(
            memory_id="memory-personality-context",
            run_id=run_id,
            source_session_id=session_id,
            memory_type="disclosed_experience",
            information_class="explicit_disclosure",
            content="The client reported tension during meetings.",
            confidence=0.95,
            memory_version=1,
            memory_scope="episodic",
            created_at=NOW,
            updated_at=NOW,
        )
        memory.add_evidence(
            "memory-personality-context",
            patient_message_id,
            "supports",
        )

    # Retiring the profile must not change the version already pinned by this Run.
    personality_service.retire_profile(profile.personality_profile_id)

    system["disclosures"].initialize_run_disclosures(
        run_id,
        created_at=NOW,
    )

    context = system["service"].build_patient_context(
        run_id,
        session_id,
        therapist_message_id,
    )

    assert context.character_personality is not None
    assert context.character_personality.configured is True
    assert context.character_personality.profile_version == 1

    assert context.character_state is not None
    character_values = {
        item.name: item.value
        for item in context.character_state.values
    }
    assert character_values == profile.initial_state

    assert len(context.longitudinal_memory) == 1
    assert context.longitudinal_memory[0].memory_scope == "episodic"

    payload = patient_context_to_payload(context)

    profile_payload = payload["character_personality"]["profile_data"]
    assert profile_payload["communication_style"] == ["careful", "measured"]
    assert "authoring_notes" not in profile_payload
    assert "initial_state" not in profile_payload
    assert "personality_profile_id" not in profile_payload

    assert payload["longitudinal_memory"][0]["memory_scope"] == "episodic"
