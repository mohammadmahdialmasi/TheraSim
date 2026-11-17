import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.llm.client import ProviderConnectionError
from app.llm.patient_agent import PatientAgent
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import (
    AuditRepository,
    ModelRunRepository,
)
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.services.interactions import (
    InteractionAttemptOwnershipLostError,
    InteractionGenerationError,
    InteractionIdempotencyConflictError,
    InteractionService,
    InteractionSessionBusyError,
)
from app.services.patient_context import (
    FrozenJSONObject,
    PatientContext,
    PatientIdentity,
    PatientState,
    PatientStateVariable,
    PatientTranscriptMessage,
    RestrictedProfileContext,
    STATE_VARIABLES,
)


NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    database = DatabaseManager(data_dir=tmp_path / "interaction-service")
    database.initialize()

    with database.transaction("operational") as connection:
        cases = CaseRepository(connection)
        cases.create_case(
            case_id="case-1",
            case_code="CASE-001",
            display_name="Ava",
            status="active",
            created_at=NOW_TEXT,
            updated_at=NOW_TEXT,
        )
        cases.create_case_version(
            case_version_id="version-1",
            case_id="case-1",
            version_number="1.0",
            modality="ACT",
            language="fa",
            schema_version="0.2",
            created_at=NOW_TEXT,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="fa",
            configuration_version="0.1",
            created_at=NOW_TEXT,
            started_at=NOW_TEXT,
            status="active",
        )
        SessionRepository(connection).create_session(
            session_id="session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW_TEXT,
            started_at=NOW_TEXT,
        )

    return database


class FakeContextService:
    def __init__(self, manager):
        self.manager = manager
        self.calls = []

    def build_patient_context(self, run_id, session_id, therapist_message_id):
        self.calls.append((run_id, session_id, therapist_message_id))

        with self.manager.connection("operational") as connection:
            message = MessageRepository(connection).get_message(
                therapist_message_id
            )
            session = SessionRepository(connection).get_session(session_id)

        empty = FrozenJSONObject(())
        state = PatientState(
            snapshot_id="snapshot-test",
            state_schema_version="1",
            values=tuple(
                PatientStateVariable(name=name, value=1)
                for name in sorted(STATE_VARIABLES)
            ),
        )

        therapist = PatientTranscriptMessage(
            message_id=message["message_id"],
            session_id=message["session_id"],
            session_number=session["session_number"],
            sequence_number=message["sequence_number"],
            role="therapist",
            content=message["content"],
            created_at=message["created_at"],
        )

        return PatientContext(
            case_id="case-1",
            case_version_id="version-1",
            run_id=run_id,
            session_id=session_id,
            session_number=session["session_number"],
            language="fa",
            modality="ACT",
            public_identity=PatientIdentity(
                display_name="Ava",
                age=29,
                occupation="Designer",
                presenting_concerns=("Anxiety",),
                initial_disclosure=None,
            ),
            restricted_profile=RestrictedProfileContext(
                clinical_formulation=empty,
                relevant_personal_history=empty,
                maintaining_factors=(),
                avoidance_patterns=(),
                hypothesized_functions=empty,
                initial_safety_baseline=empty,
                patient_simulation_instructions=None,
            ),
            relevant_case_facts=(),
            current_state=state,
            longitudinal_memory=(),
            recent_transcript=(),
            therapist_message=therapist,
        )


class FakeProviderClient:
    def __init__(self):
        self.config = Settings.from_environment({
            "OLLAMA_MODEL": "local-test-model",
        }).get_provider("ollama")
        self.calls = []
        self.error = None
        self.reply_content = "امروز کمی مضطرب هستم."
        self.on_call = None

    def chat(self, model, messages, temperature=None, max_tokens=None):
        self.calls.append({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })

        if self.on_call is not None:
            self.on_call()

        if self.error is not None:
            raise self.error

        return {
            "content": json.dumps(
                {"content": self.reply_content},
                ensure_ascii=False,
            ),
            "model": "local-test-model",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 12,
                "total_tokens": 62,
            },
        }


@pytest.fixture
def system(manager):
    client = FakeProviderClient()
    agent = PatientAgent(client, temperature=0.4, max_tokens=256)
    context_service = FakeContextService(manager)
    current_time = [NOW]
    next_id = iter(range(1, 10000))

    service = InteractionService(
        manager,
        agent,
        context_service,
        request_timeout_seconds=3,
        lease_grace_seconds=2,
        clock=lambda: current_time[0],
        id_factory=lambda: str(next(next_id)),
    )

    return {
        "manager": manager,
        "client": client,
        "agent": agent,
        "context_service": context_service,
        "clock": current_time,
        "service": service,
    }


def _request_hash(content):
    serialized = json.dumps(
        {"content": content},
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def test_handle_message_persists_validated_response_and_model_metadata(system):
    manager = system["manager"]

    def assert_provider_runs_without_write_transaction():
        with manager.connection("operational") as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()

    system["client"].on_call = assert_provider_runs_without_write_transaction

    result = system["service"].handle_message(
        "session-1",
        "idempotency-1",
        "در جلسه متوجه اضطرابم شدم.",
    )

    assert result.status == "completed"
    assert result.attempt_number == 1
    assert result.therapist_content == "در جلسه متوجه اضطرابم شدم."
    assert result.patient_content == "امروز کمی مضطرب هستم."
    assert result.patient_message_id is not None

    assert len(system["client"].calls) == 1
    assert system["context_service"].calls == [
        ("run-1", "session-1", result.therapist_message_id)
    ]

    with manager.connection("operational") as connection:
        messages = MessageRepository(connection).list_by_session("session-1")
        request = InteractionRequestRepository(connection).get_by_idempotency_key(
            "session-1",
            "idempotency-1",
        )
        model = ModelRunRepository(connection).get(
            request["last_model_run_id"]
        )
        events = EventRepository(connection).list_by_run("run-1")
        extraction_job = connection.execute(
            """
            SELECT run_id, session_id, interaction_request_id, status,
                   attempt_count
            FROM memory_extraction_jobs
            WHERE interaction_request_id = ?
            """,
            (request["request_id"],),
        ).fetchone()
        event_evidence = [
            EventRepository(connection).list_evidence(event["event_id"])[0]
            for event in events
        ]
        audits = AuditRepository(connection).list_for_entity(
            "interaction_request",
            request["request_id"],
        )

    assert [item["role"] for item in messages] == ["therapist", "patient"]
    assert request["processing_status"] == "completed"
    assert request["attempt_number"] == 1
    assert tuple(extraction_job) == (
        "run-1",
        "session-1",
        request["request_id"],
        "pending",
        0,
    )
    assert model["execution_status"] == "completed"
    assert model["input_hash"].startswith("sha256:")
    assert model["output_hash"].startswith("sha256:")
    assert model["output_validation_status"] == "valid"
    assert [event["event_type"] for event in events] == [
        "therapist_message_received",
        "patient_response_generated",
    ]
    assert [
        evidence["message_id"]
        for evidence in event_evidence
    ] == [
        result.therapist_message_id,
        result.patient_message_id,
    ]
    assert len(audits) == 2


def test_completed_idempotent_replay_does_not_call_provider_again(system):
    first = system["service"].handle_message(
        "session-1",
        "same-key",
        "وقتی سکوت می‌کنم چه اتفاقی می‌افتد؟",
    )
    second = system["service"].handle_message(
        "session-1",
        "same-key",
        "وقتی سکوت می‌کنم چه اتفاقی می‌افتد؟",
    )

    assert first == second
    assert len(system["client"].calls) == 1

    with system["manager"].connection("operational") as connection:
        messages = MessageRepository(connection).list_by_session("session-1")
        events = EventRepository(connection).list_by_run("run-1")
        jobs = connection.execute(
            "SELECT COUNT(*) FROM memory_extraction_jobs"
        ).fetchone()[0]

    assert len(messages) == 2
    assert len(events) == 2
    assert jobs == 1


def test_events_are_ordered_across_completed_interactions(system):
    system["service"].handle_message(
        "session-1",
        "first-turn",
        "از آن اتفاق چه چیزی در ذهنتان مانده است؟",
    )
    system["service"].handle_message(
        "session-1",
        "second-turn",
        "بعد از آن چه کردید؟",
    )

    with system["manager"].connection("operational") as connection:
        events = EventRepository(connection).list_by_run("run-1")

    assert [event["sequence_number"] for event in events] == [1, 2, 3, 4]
    assert [
        event["event_type"]
        for event in events
    ] == [
        "therapist_message_received",
        "patient_response_generated",
        "therapist_message_received",
        "patient_response_generated",
    ]


def test_idempotency_key_rejects_changed_payload(system):
    system["service"].handle_message(
        "session-1",
        "conflict-key",
        "متن اول",
    )

    with pytest.raises(InteractionIdempotencyConflictError):
        system["service"].handle_message(
            "session-1",
            "conflict-key",
            "متن متفاوت",
        )

    assert len(system["client"].calls) == 1


def test_new_idempotency_key_is_blocked_by_unresolved_request(system):
    with system["manager"].transaction("operational") as connection:
        InteractionRequestRepository(connection).create_request(
            request_id="pending-request",
            session_id="session-1",
            idempotency_key="pending-key",
            request_hash=_request_hash("pending"),
            created_at=NOW_TEXT,
        )

    with pytest.raises(InteractionSessionBusyError):
        system["service"].handle_message(
            "session-1",
            "new-key",
            "درخواست تازه",
        )

    assert system["client"].calls == []


def test_failed_generation_is_recoverable_with_same_therapist_message(system):
    system["client"].error = ProviderConnectionError("private provider detail")

    with pytest.raises(InteractionGenerationError) as captured:
        system["service"].handle_message(
            "session-1",
            "recoverable-key",
            "در جلسات کاری مضطرب می‌شوم.",
        )

    assert captured.value.error_code == "provider_unavailable"
    assert "private provider detail" not in str(captured.value)

    with system["manager"].connection("operational") as connection:
        requests = InteractionRequestRepository(connection)
        failed = requests.get_by_idempotency_key(
            "session-1",
            "recoverable-key",
        )
        therapist_message_id = failed["therapist_message_id"]
        old_model = ModelRunRepository(connection).get(
            failed["last_model_run_id"]
        )

    assert failed["processing_status"] == "failed"
    assert old_model["execution_status"] == "failed"

    with system["manager"].connection("operational") as connection:
        assert EventRepository(connection).list_by_run("run-1") == []
        assert connection.execute(
            "SELECT COUNT(*) FROM memory_extraction_jobs"
        ).fetchone()[0] == 0

    system["client"].error = None

    recovered = system["service"].handle_message(
        "session-1",
        "recoverable-key",
        "در جلسات کاری مضطرب می‌شوم.",
    )

    assert recovered.status == "completed"
    assert recovered.attempt_number == 2
    assert recovered.therapist_message_id == therapist_message_id
    assert len(system["client"].calls) == 2

    with system["manager"].connection("operational") as connection:
        messages = MessageRepository(connection).list_by_session("session-1")
        request = InteractionRequestRepository(connection).get_by_idempotency_key(
            "session-1",
            "recoverable-key",
        )
        events = EventRepository(connection).list_by_run("run-1")

    assert [message["role"] for message in messages] == ["therapist", "patient"]
    assert request["processing_status"] == "completed"
    assert request["attempt_number"] == 2
    assert len(events) == 2


def test_expired_attempt_cannot_persist_late_patient_response(system):
    late_ids = iter(range(1, 100))
    system["service"] = InteractionService(
        system["manager"],
        system["agent"],
        system["context_service"],
        request_timeout_seconds=1,
        lease_grace_seconds=0,
        clock=lambda: system["clock"][0],
        id_factory=lambda: "late-" + str(next(late_ids)),
    )

    def advance_clock_after_provider_call():
        system["clock"][0] = NOW + timedelta(seconds=2)

    system["client"].on_call = advance_clock_after_provider_call

    with pytest.raises(InteractionAttemptOwnershipLostError):
        system["service"].handle_message(
            "session-1",
            "late-key",
            "پاسخ دیرهنگام نباید ذخیره شود.",
        )

    with system["manager"].connection("operational") as connection:
        requests = InteractionRequestRepository(connection)
        request = requests.get_by_idempotency_key("session-1", "late-key")
        messages = MessageRepository(connection).list_by_session("session-1")
        model = ModelRunRepository(connection).get(request["last_model_run_id"])

    assert request["processing_status"] == "in_progress"
    assert request["patient_message_id"] is None
    assert model["execution_status"] == "failed"
    assert [message["role"] for message in messages] == ["therapist"]

    system["client"].on_call = None

    recovered = system["service"].handle_message(
        "session-1",
        "late-key",
        "پاسخ دیرهنگام نباید ذخیره شود.",
    )

    assert recovered.status == "completed"
    assert recovered.attempt_number == 2

    with system["manager"].connection("operational") as connection:
        messages = MessageRepository(connection).list_by_session("session-1")

    assert [message["role"] for message in messages] == ["therapist", "patient"]
