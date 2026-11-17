import json
import sqlite3
from uuid import uuid4

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories import (
    CaseRepository,
    InteractionRequestRepository,
    MessageRepository,
    SessionOrderError,
    SessionRepository,
    SimulationRunRepository,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "repository-data")
    result.initialize()
    return result


def make_case_and_run(connection):
    token = uuid4().hex

    case_id = f"case-{token}"
    version_id = f"version-{token}"
    run_id = f"run-{token}"

    cases = CaseRepository(connection)
    cases.create_case(
        case_id=case_id,
        case_code=f"TEST-{token[:12]}",
        display_name="Synthetic test case",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    cases.create_case_version(
        case_version_id=version_id,
        case_id=case_id,
        version_number="0.2",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )

    runs = SimulationRunRepository(connection)
    runs.create_run(
        run_id=run_id,
        case_id=case_id,
        case_version_id=version_id,
        modality="ACT",
        language="fa",
        configuration_version="0.1",
        created_at=NOW,
    )

    return {
        "case_id": case_id,
        "version_id": version_id,
        "run_id": run_id,
    }


def test_case_repository_creates_and_reads_case_version_and_profile(manager):
    with manager.transaction("operational") as connection:
        repo = CaseRepository(connection)
        ids = make_case_and_run(connection)

        case = repo.get_case(ids["case_id"])
        assert case is not None
        assert case["status"] == "active"

        assert repo.get_case_by_code(case["case_code"])["case_id"] == (
            ids["case_id"]
        )

        version = repo.get_case_version(ids["version_id"])
        assert version is not None
        assert version["modality"] == "ACT"

        assert repo.get_case_version_for_case(
            ids["case_id"], ids["version_id"]
        ) is not None

        repo.create_public_profile(
            case_version_id=ids["version_id"],
            age=29,
            occupation="UX Designer",
            presenting_concerns=["meeting anxiety", "avoidance"],
            initial_disclosure="I hesitate to share ideas at work.",
            profile_metadata={"language": "fa"},
            created_at=NOW,
        )

        profile = repo.get_public_profile(ids["version_id"])
        assert profile is not None
        assert json.loads(profile["presenting_concerns"]) == [
            "meeting anxiety",
            "avoidance",
        ]
        assert json.loads(profile["profile_metadata"]) == {"language": "fa"}

        assert len(repo.list_case_versions(ids["case_id"])) == 1
        assert len(repo.list_cases(status="active")) == 1


def test_case_repository_validates_inputs(manager):
    with manager.connection("operational") as connection:
        repo = CaseRepository(connection)

        with pytest.raises(ValueError):
            repo.create_case(
                case_id="case-x",
                case_code="CASE-X",
                display_name="Test",
                status="unknown",
                created_at=NOW,
                updated_at=NOW,
            )

        with pytest.raises(ValueError):
            repo.list_cases(limit=500)

        with pytest.raises(ValueError):
            repo.create_public_profile(
                case_version_id="version-x",
                age=0,
                created_at=NOW,
            )


def test_run_repository_creates_lists_and_updates_status(manager):
    with manager.transaction("operational") as connection:
        ids = make_case_and_run(connection)
        repo = SimulationRunRepository(connection)

        run = repo.get_run(ids["run_id"])
        assert run is not None
        assert run["status"] == "initialized"

        assert repo.update_status(
            ids["run_id"],
            "active",
            started_at=NOW,
        )

        updated = repo.get_run(ids["run_id"])
        assert updated["status"] == "active"
        assert updated["started_at"] == NOW

        assert len(repo.list_runs(status="active")) == 1

        assert not repo.update_status(
            "missing-run",
            "completed",
            completed_at=NOW,
        )


def test_session_repository_enforces_sequential_completion_without_a_limit(manager):
    with manager.transaction("operational") as connection:
        ids = make_case_and_run(connection)
        repo = SessionRepository(connection)

        for expected_number in range(1, 6):
            number = repo.create_next_session(
                session_id=f"session-{expected_number}",
                run_id=ids["run_id"],
                created_at=NOW,
                status="active",
            )
            assert number == expected_number

            if expected_number == 1:
                with pytest.raises(SessionOrderError):
                    repo.next_session_number(ids["run_id"])

            assert repo.update_status(
                f"session-{expected_number}",
                "completed",
                ended_at=NOW,
            )

        assert [row["session_number"] for row in repo.list_by_run(
            ids["run_id"]
        )] == [1, 2, 3, 4, 5]


def test_message_repository_sequences_messages_per_session(manager):
    with manager.transaction("operational") as connection:
        ids = make_case_and_run(connection)
        sessions = SessionRepository(connection)
        sessions.create_session(
            session_id="session-message-test",
            run_id=ids["run_id"],
            session_number=1,
            created_at=NOW,
            status="active",
        )

        repo = MessageRepository(connection)

        assert repo.next_sequence_number("session-message-test") == 1

        repo.create_message(
            message_id="message-1",
            session_id="session-message-test",
            sequence_number=1,
            role="therapist",
            content="What happened in the meeting?",
            created_at=NOW,
        )

        assert repo.next_sequence_number("session-message-test") == 2

        repo.create_message(
            message_id="message-2",
            session_id="session-message-test",
            sequence_number=2,
            role="patient",
            content="I hesitated to speak.",
            created_at=NOW,
        )

        messages = repo.list_by_session("session-message-test")
        assert [row["sequence_number"] for row in messages] == [1, 2]
        assert repo.get_message("message-2")["role"] == "patient"

        with pytest.raises(ValueError):
            repo.create_message(
                message_id="message-invalid",
                session_id="session-message-test",
                sequence_number=3,
                role="system",
                content="Not a permitted role",
                created_at=NOW,
            )


def test_interaction_repository_supports_idempotency_and_completion(manager):
    with manager.transaction("operational") as connection:
        ids = make_case_and_run(connection)
        SessionRepository(connection).create_session(
            session_id="session-interaction",
            run_id=ids["run_id"],
            session_number=1,
            created_at=NOW,
            status="active",
        )

        requests = InteractionRequestRepository(connection)
        messages = MessageRepository(connection)

        requests.create_request(
            request_id="request-1",
            session_id="session-interaction",
            idempotency_key="operation-001",
            request_hash="sha256:payload-001",
            created_at=NOW,
        )

        found = requests.get_by_idempotency_key(
            "session-interaction",
            "operation-001",
        )
        assert found is not None
        assert found["request_hash"] == "sha256:payload-001"
        assert found["processing_status"] == "in_progress"

        with pytest.raises(sqlite3.IntegrityError):
            requests.create_request(
                request_id="request-duplicate",
                session_id="session-interaction",
                idempotency_key="operation-001",
                request_hash="sha256:payload-002",
                created_at=NOW,
            )

        messages.create_message(
            message_id="therapist-message",
            session_id="session-interaction",
            sequence_number=1,
            role="therapist",
            content="Can you describe the meeting?",
            created_at=NOW,
        )

        requests.attach_therapist_message(
            "request-1",
            "therapist-message",
        )

        assert requests.claim_attempt(
            "request-1",
            "attempt-1",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        requests.mark_failed(
            "request-1",
            "MODEL_EXECUTION_FAILED",
            attempt_token="attempt-1",
            failed_at="2026-11-16T12:01:00Z",
        )
        assert requests.get_request("request-1")["processing_status"] == "failed"

        assert requests.claim_attempt(
            "request-1",
            "attempt-2",
            now="2026-11-16T12:02:00Z",
            lease_expires_at="2026-11-16T12:07:00Z",
        )

        messages.create_message(
            message_id="patient-message",
            session_id="session-interaction",
            sequence_number=2,
            role="patient",
            content="I felt nervous.",
            created_at=NOW,
        )

        requests.mark_completed(
            "request-1",
            "patient-message",
            "2026-11-16T12:03:00Z",
            attempt_token="attempt-2",
        )

        completed = requests.get_request("request-1")
        assert completed["processing_status"] == "completed"
        assert completed["patient_message_id"] == "patient-message"
        assert completed["error_code"] is None

        # Replaying the same completed result is a no-op.
        requests.mark_completed(
            "request-1",
            "patient-message",
            "2026-11-16T12:03:00Z",
            attempt_token="attempt-2",
        )

        with pytest.raises(ValueError):
            requests.mark_failed(
                "request-1",
                "LATE_FAILURE",
                attempt_token="attempt-2",
                failed_at="2026-11-16T12:04:00Z",
            )


def test_interaction_repository_rejects_cross_session_and_wrong_role_messages(
    manager,
):
    with manager.transaction("operational") as connection:
        ids = make_case_and_run(connection)
        sessions = SessionRepository(connection)

        sessions.create_session(
            session_id="session-a",
            run_id=ids["run_id"],
            session_number=1,
            created_at=NOW,
            status="active",
        )
        sessions.create_session(
            session_id="session-b",
            run_id=ids["run_id"],
            session_number=2,
            created_at=NOW,
            status="initialized",
        )

        messages = MessageRepository(connection)
        requests = InteractionRequestRepository(connection)

        requests.create_request(
            request_id="request-a",
            session_id="session-a",
            idempotency_key="key-a",
            request_hash="hash-a",
            created_at=NOW,
        )

        messages.create_message(
            message_id="message-in-b",
            session_id="session-b",
            sequence_number=1,
            role="therapist",
            content="Message in another session.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-in-a",
            session_id="session-a",
            sequence_number=1,
            role="therapist",
            content="Therapist message in session A.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="patient-in-a",
            session_id="session-a",
            sequence_number=2,
            role="patient",
            content="Patient response.",
            created_at=NOW,
        )

        with pytest.raises(ValueError):
            requests.attach_therapist_message(
                "request-a",
                "message-in-b",
            )

        requests.attach_therapist_message(
            "request-a",
            "therapist-in-a",
        )

        assert requests.claim_attempt(
            "request-a",
            "attempt-a",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        with pytest.raises(ValueError, match="role"):
            requests.mark_completed(
                "request-a",
                "therapist-in-a",
                "2026-11-16T12:01:00Z",
                attempt_token="attempt-a",
            )


def test_repository_does_not_commit_or_own_caller_transaction(manager):
    with manager.connection("operational") as connection:
        repo = CaseRepository(connection)

        connection.execute("BEGIN")

        repo.create_case(
            case_id="rollback-case",
            case_code="ROLLBACK-CASE",
            display_name="Rollback test",
            created_at=NOW,
            updated_at=NOW,
        )

        assert connection.in_transaction

        connection.rollback()

        assert repo.get_case("rollback-case") is None
