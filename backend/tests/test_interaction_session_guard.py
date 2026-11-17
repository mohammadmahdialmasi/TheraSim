import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.simulation_runs import SimulationRunRepository
from app.persistence.repositories.operations import ModelRunRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "interaction-guard")
    result.initialize()
    return result


@pytest.fixture
def seeded_session(manager):
    with manager.transaction("operational") as connection:
        CaseRepository(connection).create_case(
            case_id="case-1",
            case_code="TEST-CASE-1",
            display_name="Synthetic Test Case",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )

        CaseRepository(connection).create_case_version(
            case_version_id="version-1",
            case_id="case-1",
            version_number="1.0",
            modality="ACT",
            language="fa",
            schema_version="0.2",
            created_at=NOW,
        )

        SimulationRunRepository(connection).create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="fa",
            configuration_version="0.1",
            created_at=NOW,
            status="active",
        )

        SessionRepository(connection).create_session(
            session_id="session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW,
        )

    return "session-1"


def test_empty_session_has_no_unresolved_requests(manager, seeded_session):
    with manager.connection("operational") as connection:
        repository = InteractionRequestRepository(connection)

        assert repository.count_unresolved_by_session(
            seeded_session
        ) == 0


def test_in_progress_and_failed_requests_are_unresolved(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        repository = InteractionRequestRepository(connection)

        repository.create_request(
            request_id="request-1",
            session_id=seeded_session,
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

        MessageRepository(connection).create_message(
            message_id="therapist-failed-1",
            session_id=seeded_session,
            sequence_number=1,
            role="therapist",
            content="I would like to understand what happened.",
            created_at=NOW,
        )

        repository.attach_therapist_message(
            "request-1",
            "therapist-failed-1",
        )

        assert repository.count_unresolved_by_session(
            seeded_session
        ) == 1

        assert repository.claim_attempt(
            "request-1",
            "attempt-failed-1",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        repository.mark_failed(
            "request-1",
            "provider_unavailable",
            attempt_token="attempt-failed-1",
            failed_at="2026-11-16T12:01:00Z",
        )

        assert repository.count_unresolved_by_session(
            seeded_session
        ) == 1


def test_completed_request_is_not_unresolved(manager, seeded_session):
    with manager.transaction("operational") as connection:
        messages = MessageRepository(connection)

        messages.create_message(
            message_id="therapist-1",
            session_id=seeded_session,
            sequence_number=1,
            role="therapist",
            content="I would like to understand what happened.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="patient-1",
            session_id=seeded_session,
            sequence_number=2,
            role="patient",
            content="I felt anxious during the meeting.",
            created_at=NOW,
        )

        requests = InteractionRequestRepository(connection)

        requests.create_request(
            request_id="request-1",
            session_id=seeded_session,
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

        requests.attach_therapist_message(
            "request-1",
            "therapist-1",
        )

        assert requests.claim_attempt(
            "request-1",
            "attempt-complete-1",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        requests.mark_completed(
            "request-1",
            "patient-1",
            "2026-11-16T12:01:00Z",
            attempt_token="attempt-complete-1",
        )

        assert requests.count_unresolved_by_session(
            seeded_session
        ) == 0


def test_unresolved_count_is_scoped_to_session(manager, seeded_session):
    with manager.transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="session-2",
            run_id="run-1",
            session_number=2,
            status="active",
            created_at=NOW,
        )

        requests = InteractionRequestRepository(connection)

        requests.create_request(
            request_id="request-1",
            session_id=seeded_session,
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

        assert requests.count_unresolved_by_session(
            seeded_session
        ) == 1

        assert requests.count_unresolved_by_session(
            "session-2"
        ) == 0


def test_method_does_not_commit_caller_transaction(manager, seeded_session):
    connection = manager.connect("operational")

    try:
        connection.execute("BEGIN IMMEDIATE")

        repository = InteractionRequestRepository(connection)

        repository.create_request(
            request_id="request-1",
            session_id=seeded_session,
            idempotency_key="key-1",
            request_hash="hash-1",
            created_at=NOW,
        )

        repository.count_unresolved_by_session(seeded_session)

        assert connection.in_transaction

        connection.rollback()
    finally:
        connection.close()

    with manager.connection("operational") as verification:
        count = verification.execute(
            """
            SELECT COUNT(*)
            FROM interaction_requests
            WHERE request_id = ?
            """,
            ("request-1",),
        ).fetchone()[0]

        assert count == 0


def test_empty_session_id_is_rejected(manager):
    with manager.connection("operational") as connection:
        repository = InteractionRequestRepository(connection)

        with pytest.raises(ValueError, match="session_id"):
            repository.count_unresolved_by_session("")

def _seed_claimable_request(connection, session_id, suffix):
    requests = InteractionRequestRepository(connection)
    messages = MessageRepository(connection)

    request_id = f"request-{suffix}"
    therapist_message_id = f"therapist-{suffix}"

    requests.create_request(
        request_id=request_id,
        session_id=session_id,
        idempotency_key=f"key-{suffix}",
        request_hash=f"hash-{suffix}",
        created_at=NOW,
    )

    messages.create_message(
        message_id=therapist_message_id,
        session_id=session_id,
        sequence_number=1,
        role="therapist",
        content="I would like to understand what happened.",
        created_at=NOW,
    )

    requests.attach_therapist_message(request_id, therapist_message_id)
    return requests, request_id


def _create_patient_model_run(
    connection,
    session_id,
    model_run_id,
    *,
    component="patient_agent",
    execution_status="in_progress",
):
    ModelRunRepository(connection).create_model_run(
        model_run_id=model_run_id,
        run_id="run-1",
        session_id=session_id,
        component=component,
        provider="ollama",
        model_identifier="local-test-model",
        execution_status=execution_status,
        started_at=NOW,
        generation_parameters={"temperature": 0.7},
    )


def test_claim_attempt_is_exclusive_and_recoverable_after_expiry(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "exclusive"
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-first",
            now=NOW,
            lease_expires_at="2026-11-16T12:02:00Z",
        )

        assert not requests.claim_attempt(
            request_id,
            "attempt-too-early",
            now="2026-11-16T12:01:00Z",
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        current = requests.get_request(request_id)
        assert current["attempt_token"] == "attempt-first"
        assert current["attempt_number"] == 1

        assert requests.claim_attempt(
            request_id,
            "attempt-recovery",
            now="2026-11-16T12:03:00Z",
            lease_expires_at="2026-11-16T12:08:00Z",
        )

        recovered = requests.get_request(request_id)
        assert recovered["attempt_token"] == "attempt-recovery"
        assert recovered["attempt_number"] == 2
        assert recovered["processing_status"] == "in_progress"


def test_stale_attempt_cannot_complete_or_fail_after_reclaim(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "fencing"
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-old",
            now=NOW,
            lease_expires_at="2026-11-16T12:02:00Z",
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-current",
            now="2026-11-16T12:03:00Z",
            lease_expires_at="2026-11-16T12:08:00Z",
        )

        MessageRepository(connection).create_message(
            message_id="patient-fencing",
            session_id=seeded_session,
            sequence_number=2,
            role="patient",
            content="I felt anxious during the meeting.",
            created_at="2026-11-16T12:03:30Z",
        )

        with pytest.raises(ValueError, match="token"):
            requests.mark_completed(
                request_id,
                "patient-fencing",
                "2026-11-16T12:04:00Z",
                attempt_token="attempt-old",
            )

        with pytest.raises(ValueError, match="token"):
            requests.mark_failed(
                request_id,
                "stale_failure",
                attempt_token="attempt-old",
                failed_at="2026-11-16T12:04:00Z",
            )

        requests.mark_completed(
            request_id,
            "patient-fencing",
            "2026-11-16T12:04:00Z",
            attempt_token="attempt-current",
        )

        completed = requests.get_request(request_id)
        assert completed["processing_status"] == "completed"
        assert completed["patient_message_id"] == "patient-fencing"


def test_failed_attempt_can_be_reclaimed_with_a_fresh_token(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "failed-recovery"
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-failed",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        requests.mark_failed(
            request_id,
            "provider_unavailable",
            attempt_token="attempt-failed",
            failed_at="2026-11-16T12:01:00Z",
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-after-failure",
            now="2026-11-16T12:02:00Z",
            lease_expires_at="2026-11-16T12:07:00Z",
        )

        current = requests.get_request(request_id)
        assert current["attempt_number"] == 2
        assert current["attempt_token"] == "attempt-after-failure"
        assert current["error_code"] is None


def test_attempt_token_cannot_be_reused_after_failure(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "token-reuse"
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-reused",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        requests.mark_failed(
            request_id,
            "provider_unavailable",
            attempt_token="attempt-reused",
            failed_at="2026-11-16T12:01:00Z",
        )

        with pytest.raises(ValueError, match="fresh"):
            requests.claim_attempt(
                request_id,
                "attempt-reused",
                now="2026-11-16T12:02:00Z",
                lease_expires_at="2026-11-16T12:07:00Z",
            )


def test_claim_requires_attached_therapist_message(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests = InteractionRequestRepository(connection)
        requests.create_request(
            request_id="request-no-therapist",
            session_id=seeded_session,
            idempotency_key="key-no-therapist",
            request_hash="hash-no-therapist",
            created_at=NOW,
        )

        with pytest.raises(ValueError, match="Therapist input"):
            requests.claim_attempt(
                "request-no-therapist",
                "attempt-no-therapist",
                now=NOW,
                lease_expires_at="2026-11-16T12:05:00Z",
            )

        assert requests.get_request(
            "request-no-therapist"
        )["attempt_number"] == 0


def test_claim_rejects_naive_timestamps(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "naive-time"
        )

        with pytest.raises(ValueError, match="UTC timezone"):
            requests.claim_attempt(
                request_id,
                "attempt-naive",
                now="2026-11-16T12:00:00",
                lease_expires_at="2026-11-16T12:05:00Z",
            )


def test_claim_attempt_does_not_commit_caller_transaction(
    manager,
    seeded_session,
):
    connection = manager.connect("operational")

    try:
        connection.execute("BEGIN IMMEDIATE")
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "transaction"
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-transaction",
            now=NOW,
            lease_expires_at="2026-11-16T12:05:00Z",
        )

        assert connection.in_transaction
        connection.rollback()
    finally:
        connection.close()

    with manager.connection("operational") as verification:
        assert verification.execute(
            "SELECT COUNT(*) FROM interaction_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()[0] == 0

def test_claim_attempt_rejects_model_run_that_is_not_in_progress(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "completed-model-run"
        )

        _create_patient_model_run(
            connection,
            seeded_session,
            "model-run-completed",
            execution_status="completed",
        )

        with pytest.raises(ValueError, match="must be in_progress"):
            requests.claim_attempt(
                request_id,
                "attempt-completed-model",
                now=NOW,
                lease_expires_at="2026-11-16T12:05:00Z",
                model_run_id="model-run-completed",
            )

        assert requests.get_request(request_id)["attempt_number"] == 0


def test_claim_attempt_rejects_evaluator_model_run(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "evaluator-model-run"
        )

        _create_patient_model_run(
            connection,
            seeded_session,
            "model-run-evaluator",
            component="evaluator_agent",
        )

        with pytest.raises(ValueError, match="patient-agent"):
            requests.claim_attempt(
                request_id,
                "attempt-evaluator-model",
                now=NOW,
                lease_expires_at="2026-11-16T12:05:00Z",
                model_run_id="model-run-evaluator",
            )

        assert requests.get_request(request_id)["attempt_number"] == 0


def test_assert_attempt_owned_fences_stale_model_runs_and_expired_leases(
    manager,
    seeded_session,
):
    with manager.transaction("operational") as connection:
        requests, request_id = _seed_claimable_request(
            connection, seeded_session, "ownership-assertion"
        )

        _create_patient_model_run(
            connection,
            seeded_session,
            "model-run-old",
        )
        _create_patient_model_run(
            connection,
            seeded_session,
            "model-run-current",
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-old",
            now=NOW,
            lease_expires_at="2026-11-16T12:02:00Z",
            model_run_id="model-run-old",
        )

        assert requests.claim_attempt(
            request_id,
            "attempt-current",
            now="2026-11-16T12:03:00Z",
            lease_expires_at="2026-11-16T12:08:00Z",
            model_run_id="model-run-current",
        )

        with pytest.raises(ValueError, match="token"):
            requests.assert_attempt_owned(
                request_id,
                "attempt-old",
                now="2026-11-16T12:04:00Z",
                model_run_id="model-run-old",
            )

        with pytest.raises(ValueError, match="Model run"):
            requests.assert_attempt_owned(
                request_id,
                "attempt-current",
                now="2026-11-16T12:04:00Z",
                model_run_id="model-run-old",
            )

        requests.assert_attempt_owned(
            request_id,
            "attempt-current",
            now="2026-11-16T12:04:00Z",
            model_run_id="model-run-current",
        )

        with pytest.raises(ValueError, match="lease has expired"):
            requests.assert_attempt_owned(
                request_id,
                "attempt-current",
                now="2026-11-16T12:08:00Z",
                model_run_id="model-run-current",
            )
