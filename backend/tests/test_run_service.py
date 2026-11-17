import json
import sqlite3

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.services.cases import CaseService
from app.services.runs import (
    RunCaseInactiveError,
    RunCaseNotFoundError,
    RunCaseVersionNotFoundError,
    RunConflictError,
    RunNotFoundError,
    RunProtocolConfigurationError,
    RunService,
    RunStateTransitionError,
    RestrictedProfileNotFoundError,
    SimulationRunRecord,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "run-service-tests")
    result.initialize()
    return result


@pytest.fixture
def services(manager):
    return {
        "cases": CaseService(manager),
        "runs": RunService(manager),
        "manager": manager,
    }


def seed_case(
    services,
    *,
    case_id="case-1",
    version_id="version-1",
    status="active",
    create_profile=True,
):
    cases = services["cases"]

    cases.create_case(
        case_id=case_id,
        case_code=f"CODE-{case_id}",
        display_name=f"Synthetic {case_id}",
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )

    cases.create_case_version(
        case_version_id=version_id,
        case_id=case_id,
        version_number="1.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )

    if create_profile:
        with services["manager"].transaction(
            "restricted"
        ) as connection:
            RestrictedCaseRepository(connection).create_profile(
                restricted_profile_id=f"profile-{version_id}",
                case_id=case_id,
                case_version_id=version_id,
                clinical_formulation={"type": "synthetic"},
                created_at=NOW,
            )


def create_run(services, *, run_id="run-1"):
    seed_case(services)

    return services["runs"].create_run(
        run_id=run_id,
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )


def test_create_run_validates_both_databases_and_returns_dto(services):
    result = create_run(services)

    assert isinstance(result, SimulationRunRecord)
    assert result.run_id == "run-1"
    assert result.case_id == "case-1"
    assert result.case_version_id == "version-1"
    assert result.modality == "ACT"
    assert result.language == "fa"
    assert result.status == "initialized"
    assert result.protocol_id == "ACT_EDUCATIONAL_SIMULATION"
    assert result.protocol_version == "0.1"
    assert result.session_planning_policy == "flexible"
    assert result.evaluation_rubric_id == "ACT_RUBRIC_V0"
    assert result.evaluation_rubric_version == "0.2"
    assert result.started_at is None
    assert result.completed_at is None

    stored = services["runs"].get_run("run-1")
    assert stored == result

    audits = services["manager"]

    with audits.connection("operational") as connection:
        events = AuditRepository(connection).list_for_entity(
            "simulation_run",
            "run-1",
        )

    assert len(events) == 1
    assert events[0]["operation_type"] == "run_created"

    metadata = json.loads(events[0]["metadata"])
    assert metadata["case_id"] == "case-1"
    assert metadata["initial_status"] == "initialized"
    assert metadata["session_planning_policy"] == "flexible"


def test_run_preserves_selected_planning_policy_and_rejects_configuration_edits(
    services,
):
    seed_case(services)
    result = services["runs"].create_run(
        run_id="run-milestone",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
        session_planning_policy="milestone_based",
    )

    assert result.session_planning_policy == "milestone_based"
    assert services["runs"].get_run("run-milestone").session_planning_policy == (
        "milestone_based"
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="simulation_run_configuration_is_immutable",
    ):
        with services["manager"].transaction("operational") as connection:
            connection.execute(
                """
                UPDATE simulation_runs
                SET protocol_version = '0.2'
                WHERE run_id = 'run-milestone'
                """
            )


def test_run_rejects_unregistered_protocol_versions(services):
    seed_case(services)

    with pytest.raises(RunProtocolConfigurationError):
        services["runs"].create_run(
            run_id="run-unsupported",
            case_id="case-1",
            case_version_id="version-1",
            configuration_version="0.1",
            created_at=NOW,
            protocol_version="99.0",
        )


def test_run_creation_rejects_missing_case(services):
    with pytest.raises(RunCaseNotFoundError):
        services["runs"].create_run(
            run_id="run-1",
            case_id="missing-case",
            case_version_id="missing-version",
            configuration_version="0.1",
            created_at=NOW,
        )

    assert services["runs"].get_run("run-1") is None


def test_run_creation_rejects_inactive_case(services):
    seed_case(services, status="draft")

    with pytest.raises(RunCaseInactiveError):
        services["runs"].create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            configuration_version="0.1",
            created_at=NOW,
        )

    assert services["runs"].get_run("run-1") is None


def test_run_creation_rejects_version_from_another_case(services):
    seed_case(services, case_id="case-1", version_id="version-1")
    seed_case(services, case_id="case-2", version_id="version-2")

    with pytest.raises(RunCaseVersionNotFoundError):
        services["runs"].create_run(
            run_id="run-invalid",
            case_id="case-1",
            case_version_id="version-2",
            configuration_version="0.1",
            created_at=NOW,
        )

    assert services["runs"].get_run("run-invalid") is None


def test_run_creation_requires_matching_restricted_profile(services):
    seed_case(
        services,
        case_id="case-1",
        version_id="version-1",
        create_profile=False,
    )

    with pytest.raises(RestrictedProfileNotFoundError):
        services["runs"].create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            configuration_version="0.1",
            created_at=NOW,
        )

    assert services["runs"].get_run("run-1") is None


def test_duplicate_run_identifier_is_reported_as_conflict(services):
    create_run(services)

    with pytest.raises(RunConflictError):
        services["runs"].create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            configuration_version="0.1",
            created_at=NOW,
        )


def test_list_runs_filters_and_paginates(services):
    create_run(services)

    runs = services["runs"].list_runs(status="initialized")

    assert len(runs) == 1
    assert runs[0].run_id == "run-1"

    assert services["runs"].list_runs(status="active") == []
    assert len(services["runs"].list_runs(limit=1)) == 1


def test_run_lifecycle_supports_start_interrupt_and_resume(services):
    create_run(services)

    runs = services["runs"]

    started = runs.start_run(
        "run-1",
        started_at="2026-11-16T12:01:00Z",
    )

    assert started.status == "active"
    assert started.started_at == "2026-11-16T12:01:00Z"

    interrupted = runs.interrupt_run(
        "run-1",
        interrupted_at="2026-11-16T12:02:00Z",
    )

    assert interrupted.status == "interrupted"

    resumed = runs.resume_run(
        "run-1",
        resumed_at="2026-11-16T12:03:00Z",
    )

    assert resumed.status == "active"
    assert resumed.started_at == started.started_at

    with services["manager"].connection(
        "operational"
    ) as connection:
        events = AuditRepository(connection).list_for_entity(
            "simulation_run",
            "run-1",
        )

    assert len(events) == 4


def test_run_cannot_complete_without_any_sessions(services):
    create_run(services)
    services["runs"].start_run(
        "run-1",
        started_at=NOW,
    )

    with pytest.raises(RunStateTransitionError, match="at least one"):
        services["runs"].complete_run(
            "run-1",
            completed_at=NOW,
        )

    assert services["runs"].get_run("run-1").status == "active"


@pytest.mark.parametrize("session_count", [1, 2, 5])
def test_run_completes_after_any_number_of_completed_sessions(
    services,
    session_count,
):
    create_run(services)
    services["runs"].start_run(
        "run-1",
        started_at=NOW,
    )

    with services["manager"].transaction(
        "operational"
    ) as connection:
        repository = SessionRepository(connection)

        for number in range(1, session_count + 1):
            repository.create_session(
                session_id=f"session-{number}",
                run_id="run-1",
                session_number=number,
                status="completed",
                created_at=NOW,
                ended_at=NOW,
            )

    completed = services["runs"].complete_run(
        "run-1",
        completed_at="2026-11-16T13:00:00Z",
    )

    assert completed.status == "completed"
    assert completed.completed_at == "2026-11-16T13:00:00Z"

    with pytest.raises(RunStateTransitionError):
        services["runs"].resume_run(
            "run-1",
            resumed_at=NOW,
        )


def test_run_cannot_complete_if_any_created_session_is_incomplete(services):
    create_run(services)
    services["runs"].start_run(
        "run-1",
        started_at=NOW,
    )

    with services["manager"].transaction(
        "operational"
    ) as connection:
        repository = SessionRepository(connection)

        for number in (1, 2):
            repository.create_session(
                session_id=f"session-{number}",
                run_id="run-1",
                session_number=number,
                status="completed" if number == 1 else "active",
                created_at=NOW,
            )

    with pytest.raises(RunStateTransitionError, match="All created sessions"):
        services["runs"].complete_run(
            "run-1",
            completed_at=NOW,
        )


def test_run_cannot_complete_with_nonsequential_sessions(services):
    create_run(services)
    services["runs"].start_run(
        "run-1",
        started_at=NOW,
    )

    with services["manager"].transaction(
        "operational"
    ) as connection:
        repository = SessionRepository(connection)
        for number in (1, 3):
            repository.create_session(
                session_id=f"session-{number}",
                run_id="run-1",
                session_number=number,
                status="completed",
                created_at=NOW,
                ended_at=NOW,
            )

    with pytest.raises(RunStateTransitionError, match="sequential"):
        services["runs"].complete_run(
            "run-1",
            completed_at=NOW,
        )


def test_failed_run_is_terminal(services):
    create_run(services)

    failed = services["runs"].fail_run(
        "run-1",
        failed_at="2026-11-16T12:01:00Z",
    )

    assert failed.status == "failed"

    with pytest.raises(RunStateTransitionError):
        services["runs"].start_run(
            "run-1",
            started_at=NOW,
        )


def test_invalid_transition_and_missing_run_are_rejected(services):
    create_run(services)

    with pytest.raises(RunStateTransitionError):
        services["runs"].interrupt_run(
            "run-1",
            interrupted_at=NOW,
        )

    with pytest.raises(RunNotFoundError):
        services["runs"].start_run(
            "missing-run",
            started_at=NOW,
        )


def test_run_service_requires_database_manager():
    with pytest.raises(TypeError, match="DatabaseManager"):
        RunService(object())



def _unknown_personality_estimate():
    from app.services.character_model import PersonalityEstimate

    return PersonalityEstimate(
        level="unknown",
        confidence="low",
        context_scope="not sufficiently established",
        rationale="No trait inference is made without sufficient evidence.",
    )


def _authored_personality_profile():
    from app.services.character_model import (
        AttachmentDimensions,
        BigFiveProfile,
        CharacterPersonalityProfile,
        InterpersonalDimensions,
    )

    estimate = _unknown_personality_estimate()
    return CharacterPersonalityProfile(
        personality_profile_id="personality-case-1-v1",
        character_id="AVA-001",
        case_id="case-1",
        case_version_id="version-1",
        theory_bundle_version="0.1",
        big_five=BigFiveProfile(
            openness=estimate,
            conscientiousness=estimate,
            extraversion=estimate,
            agreeableness=estimate,
            neuroticism=estimate,
        ),
        attachment=AttachmentDimensions(
            anxiety=estimate,
            avoidance=estimate,
        ),
        interpersonal=InterpersonalDimensions(
            agency=estimate,
            communion=estimate,
        ),
        initial_state={
            "affect_valence": -1,
            "arousal": 3,
            "perceived_safety": 1,
            "social_evaluative_threat": 4,
            "engagement": 2,
            "interpersonal_withdrawal": 3,
        },
    )


def test_run_without_active_personality_records_explicit_unconfigured_snapshot(
    services,
):
    from app.persistence.repositories.character_runtime import (
        DEFAULT_CHARACTER_STATE_VALUES,
        RunCharacterRepository,
    )

    result = create_run(services)

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        profile_snapshot = repository.get_profile_snapshot(result.run_id)
        state_snapshot = repository.get_latest_state_snapshot(result.run_id)
        state_values = repository.get_state_snapshot_values(
            state_snapshot["snapshot_id"]
        )

    assert profile_snapshot is not None
    assert profile_snapshot["personality_profile_id"] is None
    assert profile_snapshot["profile_version"] is None
    assert profile_snapshot["character_id"] == "UNCONFIGURED_CHARACTER"
    assert profile_snapshot["profile_status"] == "unconfigured"
    assert state_snapshot is not None
    assert state_values == DEFAULT_CHARACTER_STATE_VALUES


def test_run_captures_active_personality_reference_and_authored_initial_state(
    services,
):
    from app.persistence.repositories.character_runtime import RunCharacterRepository
    from app.services.character_personality_service import CharacterPersonalityService

    seed_case(services)
    personality_service = CharacterPersonalityService(services["manager"])
    authored = _authored_personality_profile()

    created = personality_service.create_profile(authored, created_at=NOW)
    assert created["authoring_status"] == "draft"
    assert created["profile_version"] == 1

    personality_service.review_profile(authored.personality_profile_id)
    personality_service.activate_profile(authored.personality_profile_id)

    result = services["runs"].create_run(
        run_id="run-with-personality",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        profile_snapshot = repository.get_profile_snapshot(result.run_id)
        state_snapshot = repository.get_latest_state_snapshot(result.run_id)
        state_values = repository.get_state_snapshot_values(
            state_snapshot["snapshot_id"]
        )

    assert profile_snapshot["personality_profile_id"] == authored.personality_profile_id
    assert profile_snapshot["profile_version"] == 1
    assert profile_snapshot["character_id"] == "AVA-001"
    assert profile_snapshot["profile_status"] == "active"
    assert profile_snapshot["source_content_hash"] == created["content_hash"]
    assert "profile_json" not in profile_snapshot.keys()
    assert state_values == authored.initial_state


def test_run_personality_reference_isolated_from_later_profile_versions(services):
    from app.persistence.repositories.character_runtime import RunCharacterRepository
    from app.services.character_personality_service import CharacterPersonalityService

    seed_case(services)
    personality_service = CharacterPersonalityService(services["manager"])
    first_profile = _authored_personality_profile()

    personality_service.create_profile(first_profile, created_at=NOW)
    personality_service.review_profile(first_profile.personality_profile_id)
    personality_service.activate_profile(first_profile.personality_profile_id)

    services["runs"].create_run(
        run_id="run-profile-v1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    personality_service.retire_profile(first_profile.personality_profile_id)

    second_profile = first_profile.model_copy(
        update={"personality_profile_id": "personality-case-1-v2"}
    )
    personality_service.create_profile(second_profile, created_at=NOW)
    personality_service.review_profile(second_profile.personality_profile_id)
    personality_service.activate_profile(second_profile.personality_profile_id)

    services["runs"].create_run(
        run_id="run-profile-v2",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        first_snapshot = repository.get_profile_snapshot("run-profile-v1")
        second_snapshot = repository.get_profile_snapshot("run-profile-v2")

    assert first_snapshot["personality_profile_id"] == "personality-case-1-v1"
    assert second_snapshot["personality_profile_id"] == "personality-case-1-v2"
    assert first_snapshot["profile_version"] == 1
    assert second_snapshot["profile_version"] == 2

def _prepare_character_transition_scenario(services):
    from app.persistence.repositories.messages import MessageRepository
    from app.services.character_state_transitions import (
        CharacterStateTransitionService,
    )

    create_run(services)
    services["runs"].start_run("run-1", started_at=NOW)

    with services["manager"].transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="transition-session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        messages = MessageRepository(connection)
        messages.create_message(
            message_id="transition-patient-1",
            session_id="transition-session-1",
            sequence_number=1,
            role="patient",
            content="I felt safer after being heard.",
            created_at=NOW,
        )
        messages.create_message(
            message_id="transition-therapist-1",
            session_id="transition-session-1",
            sequence_number=2,
            role="therapist",
            content="What changed for you?",
            created_at=NOW,
        )

    return CharacterStateTransitionService(services["manager"])


def _make_character_transition_proposal(
    *,
    proposal_id="proposal-1",
    session_id="transition-session-1",
    evidence_message_ids=("transition-patient-1",),
    previous_value=2,
    proposed_value=3,
):
    from app.services.character_model import CharacterStateTransitionProposal

    return CharacterStateTransitionProposal(
        proposal_id=proposal_id,
        run_id="run-1",
        session_id=session_id,
        variable_name="perceived_safety",
        previous_value=previous_value,
        proposed_value=proposed_value,
        evidence_message_ids=evidence_message_ids,
        rationale="The patient explicitly described feeling safer.",
        confidence=0.9,
        status="candidate",
    )


def test_character_transition_requires_review_then_accepts_atomically(services):
    from app.persistence.repositories.character_runtime import RunCharacterRepository

    service = _prepare_character_transition_scenario(services)
    proposal = _make_character_transition_proposal()

    submitted = service.submit_proposal(proposal, created_at=NOW)

    assert submitted["validation_status"] == "requires_review"
    assert submitted["accepted_value"] is None

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        initial_head = repository.get_current_state_snapshot("run-1")
        initial_values = repository.get_state_snapshot_values(
            initial_head["snapshot_id"]
        )
        snapshot_count = connection.execute(
            """
            SELECT COUNT(*) FROM character_state_snapshots
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()[0]

    assert initial_values["perceived_safety"] == 2
    assert snapshot_count == 1

    accepted = service.accept_transition(
        submitted["transition_id"],
        validated_at=NOW,
    )

    assert accepted["validation_status"] == "accepted"
    assert accepted["accepted_value"] == 3

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        head = repository.get_current_state_snapshot("run-1")
        values = repository.get_state_snapshot_values(head["snapshot_id"])
        snapshot_count = connection.execute(
            """
            SELECT COUNT(*) FROM character_state_snapshots
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()[0]

    assert values["perceived_safety"] == 3
    assert head["previous_snapshot_id"] == initial_head["snapshot_id"]
    assert snapshot_count == 2

    # Repeating acceptance must not append a second snapshot.
    repeated = service.accept_transition(
        submitted["transition_id"],
        validated_at=NOW,
    )
    assert repeated["validation_status"] == "accepted"

    with services["manager"].connection("operational") as connection:
        count = connection.execute(
            """
            SELECT COUNT(*) FROM character_state_snapshots
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()[0]

    assert count == 2


def test_character_transition_rejects_evidence_outside_its_session(services):
    from app.persistence.repositories.messages import MessageRepository
    from app.services.character_state_transitions import (
        CharacterStateTransitionEvidenceError,
    )

    service = _prepare_character_transition_scenario(services)

    with services["manager"].transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="transition-session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="transition-patient-other-session",
            session_id="transition-session-2",
            sequence_number=1,
            role="patient",
            content="A separate session disclosure.",
            created_at=NOW,
        )

    proposal = _make_character_transition_proposal(
        proposal_id="proposal-cross-session",
        evidence_message_ids=("transition-patient-other-session",),
    )

    with pytest.raises(CharacterStateTransitionEvidenceError):
        service.submit_proposal(proposal, created_at=NOW)

    therapist_only = _make_character_transition_proposal(
        proposal_id="proposal-therapist-only",
        evidence_message_ids=("transition-therapist-1",),
    )

    with pytest.raises(CharacterStateTransitionEvidenceError):
        service.submit_proposal(therapist_only, created_at=NOW)


def test_stale_character_transition_is_rejected_without_snapshot(services):
    from app.persistence.repositories.character_runtime import RunCharacterRepository

    service = _prepare_character_transition_scenario(services)

    first = service.submit_proposal(
        _make_character_transition_proposal(
            proposal_id="proposal-first",
            proposed_value=3,
        ),
        created_at=NOW,
    )
    second = service.submit_proposal(
        _make_character_transition_proposal(
            proposal_id="proposal-second",
            proposed_value=4,
        ),
        created_at=NOW,
    )

    service.accept_transition(first["transition_id"], validated_at=NOW)

    stale = service.accept_transition(
        second["transition_id"],
        validated_at=NOW,
    )

    assert stale["validation_status"] == "rejected"
    assert stale["accepted_value"] is None

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        head = repository.get_current_state_snapshot("run-1")
        values = repository.get_state_snapshot_values(head["snapshot_id"])
        count = connection.execute(
            """
            SELECT COUNT(*) FROM character_state_snapshots
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()[0]

    assert values["perceived_safety"] == 3
    assert count == 2


def test_character_transition_submission_is_idempotent(services):
    from app.services.character_state_transitions import (
        CharacterStateTransitionConflictError,
    )

    service = _prepare_character_transition_scenario(services)
    proposal = _make_character_transition_proposal()

    first = service.submit_proposal(proposal, created_at=NOW)
    repeated = service.submit_proposal(proposal, created_at=NOW)

    assert first["transition_id"] == repeated["transition_id"]

    conflicting = proposal.model_copy(update={"proposed_value": 4})

    with pytest.raises(CharacterStateTransitionConflictError):
        service.submit_proposal(conflicting, created_at=NOW)


def test_rejecting_character_transition_does_not_change_state(services):
    from app.persistence.repositories.character_runtime import RunCharacterRepository

    service = _prepare_character_transition_scenario(services)
    submitted = service.submit_proposal(
        _make_character_transition_proposal(),
        created_at=NOW,
    )

    rejected = service.reject_transition(
        submitted["transition_id"],
        validated_at=NOW,
    )

    assert rejected["validation_status"] == "rejected"
    assert rejected["accepted_value"] is None

    with services["manager"].connection("operational") as connection:
        repository = RunCharacterRepository(connection)
        head = repository.get_current_state_snapshot("run-1")
        values = repository.get_state_snapshot_values(head["snapshot_id"])
        count = connection.execute(
            """
            SELECT COUNT(*) FROM character_state_snapshots
            WHERE run_id = ?
            """,
            ("run-1",),
        ).fetchone()[0]

    assert values["perceived_safety"] == 2
    assert count == 1
