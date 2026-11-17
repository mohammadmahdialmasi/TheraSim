import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import AuditRepository
from app.services.cases import CaseService
from app.services.runs import RunService
from app.services.sessions import (
    SessionHasUnresolvedInteractionsError,
    SessionNotFoundError,
    SessionOrderViolationError,
    SessionRecord,
    SessionRunNotActiveError,
    SessionRunNotFoundError,
    SessionService,
    SessionTransitionError,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "session-service-tests")
    result.initialize()
    return result


@pytest.fixture
def services(manager):
    cases = CaseService(manager)

    cases.create_case(
        case_id="case-1",
        case_code="CASE-001",
        display_name="Synthetic Test Case",
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

    with manager.transaction("restricted") as connection:
        RestrictedCaseRepository(connection).create_profile(
            restricted_profile_id="profile-1",
            case_id="case-1",
            case_version_id="version-1",
            clinical_formulation={"synthetic": True},
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

    return {
        "manager": manager,
        "runs": runs,
        "sessions": SessionService(manager),
    }


def start_run(services):
    return services["runs"].start_run(
        "run-1",
        started_at=NOW,
    )


def create_session(services, *, session_id="session-1"):
    return services["sessions"].create_next_session(
        session_id=session_id,
        run_id="run-1",
        created_at=NOW,
    )


def test_create_first_session_returns_typed_dto_and_audit(services):
    start_run(services)

    result = create_session(services)

    assert isinstance(result, SessionRecord)
    assert result.session_id == "session-1"
    assert result.run_id == "run-1"
    assert result.session_number == 1
    assert result.status == "active"
    assert result.transcript_version == 1
    assert result.started_at == NOW

    with services["manager"].connection("operational") as connection:
        events = AuditRepository(connection).list_for_entity(
            "session",
            "session-1",
        )

    assert len(events) == 1
    assert events[0]["operation_type"] == "session_created"


def test_next_session_requires_previous_completion(services):
    start_run(services)
    create_session(services)

    with pytest.raises(SessionOrderViolationError):
        create_session(
            services,
            session_id="session-2",
        )

    services["sessions"].complete_session(
        "session-1",
        completed_at=NOW,
    )

    second = create_session(
        services,
        session_id="session-2",
    )

    assert second.session_number == 2


def test_next_session_numbers_remain_sequential(services):
    start_run(services)

    first = create_session(services)

    services["sessions"].complete_session(
        first.session_id,
        completed_at=NOW,
    )

    second = create_session(
        services,
        session_id="session-2",
    )

    services["sessions"].complete_session(
        second.session_id,
        completed_at=NOW,
    )

    third = create_session(
        services,
        session_id="session-3",
    )

    assert [
        item.session_number
        for item in services["sessions"].list_sessions("run-1")
    ] == [1, 2, 3]

    assert third.session_number == 3


def test_additional_sessions_can_be_created_after_each_completion(services):
    start_run(services)

    for number in range(1, 6):
        created = create_session(
            services,
            session_id=f"session-{number}",
        )

        services["sessions"].complete_session(
            created.session_id,
            completed_at=NOW,
        )

    sixth = create_session(services, session_id="session-6")
    assert sixth.session_number == 6


def test_session_creation_requires_existing_run(services):
    with pytest.raises(SessionRunNotActiveError):
        create_session(services)


def test_session_creation_rejects_missing_run(services):
    start_run(services)

    with pytest.raises(SessionRunNotFoundError):
        services["sessions"].create_next_session(
            session_id="session-invalid",
            run_id="missing-run",
            created_at=NOW,
        )


def test_session_creation_rejects_inactive_run(services):
    with pytest.raises(SessionRunNotActiveError):
        create_session(services)

    assert services["sessions"].list_sessions("run-1") == []


def test_completed_session_is_blocked_by_in_progress_request(services):
    start_run(services)
    create_session(services)

    with services["manager"].transaction("operational") as connection:
        InteractionRequestRepository(connection).create_request(
            request_id="request-1",
            session_id="session-1",
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

    with pytest.raises(
        SessionHasUnresolvedInteractionsError
    ) as error:
        services["sessions"].complete_session(
            "session-1",
            completed_at=NOW,
        )

    assert error.value.unresolved_count == 1
    assert services["sessions"].get_session(
        "session-1"
    ).status == "active"


def test_completed_session_is_blocked_by_failed_request(services):
    start_run(services)
    create_session(services)

    with services["manager"].transaction("operational") as connection:
        requests = InteractionRequestRepository(connection)

        requests.create_request(
            request_id="request-1",
            session_id="session-1",
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

        MessageRepository(connection).create_message(
            message_id="therapist-message-1",
            session_id="session-1",
            sequence_number=1,
            role="therapist",
            content="I would like to understand what happened.",
            created_at=NOW,
        )

        requests.attach_therapist_message(
            "request-1",
            "therapist-message-1",
        )

        assert requests.claim_attempt(
            "request-1",
            "attempt-1",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        requests.mark_failed(
            "request-1",
            "provider_unavailable",
            attempt_token="attempt-1",
            failed_at="2026-11-16T12:01:00Z",
        )

    with pytest.raises(SessionHasUnresolvedInteractionsError):
        services["sessions"].complete_session(
            "session-1",
            completed_at=NOW,
        )


def test_completed_session_is_terminal(services):
    start_run(services)
    create_session(services)

    completed = services["sessions"].complete_session(
        "session-1",
        completed_at=NOW,
    )

    assert completed.status == "completed"
    assert completed.ended_at == NOW

    with pytest.raises(SessionTransitionError):
        services["sessions"].resume_session(
            "session-1",
            resumed_at=NOW,
        )

    with pytest.raises(SessionTransitionError):
        services["sessions"].fail_session(
            "session-1",
            failed_at=NOW,
        )


def test_session_can_be_interrupted_and_resumed(services):
    start_run(services)
    create_session(services)

    interrupted = services["sessions"].interrupt_session(
        "session-1",
        interrupted_at=NOW,
    )

    assert interrupted.status == "interrupted"
    assert interrupted.ended_at is None

    resumed = services["sessions"].resume_session(
        "session-1",
        resumed_at="2026-11-16T12:10:00Z",
    )

    assert resumed.status == "active"
    assert resumed.started_at == NOW


def test_session_failure_is_terminal(services):
    start_run(services)
    create_session(services)

    failed = services["sessions"].fail_session(
        "session-1",
        failed_at=NOW,
    )

    assert failed.status == "failed"
    assert failed.ended_at == NOW

    with pytest.raises(SessionTransitionError):
        services["sessions"].resume_session(
            "session-1",
            resumed_at=NOW,
        )


def test_session_transitions_require_active_parent_run(services):
    start_run(services)
    create_session(services)

    services["runs"].interrupt_run(
        "run-1",
        interrupted_at=NOW,
    )

    with pytest.raises(SessionRunNotActiveError):
        services["sessions"].complete_session(
            "session-1",
            completed_at=NOW,
        )


def test_get_and_list_sessions_return_dtos(services):
    start_run(services)
    created = create_session(services)

    assert services["sessions"].get_session(
        created.session_id
    ) == created

    assert services["sessions"].get_session(
        "missing-session"
    ) is None

    assert services["sessions"].list_sessions("run-1") == [created]


def test_missing_session_transition_is_rejected(services):
    start_run(services)

    with pytest.raises(SessionNotFoundError):
        services["sessions"].complete_session(
            "missing-session",
            completed_at=NOW,
        )


def test_session_service_requires_database_manager():
    with pytest.raises(TypeError, match="DatabaseManager"):
        SessionService(object())
