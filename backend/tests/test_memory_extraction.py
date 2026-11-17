import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.routes.memories import get_memory_extraction_status_service
from app.api.routes.runs import get_run_service
from app.core.config import Settings
from app.llm.client import ProviderConnectionError
from app.llm.memory_extraction_agent import (
    MemoryExtractionAgent,
    MemoryExtractionAgentError,
)
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.interaction_requests import (
    InteractionRequestRepository,
)
from app.persistence.repositories.memory_extraction_jobs import (
    MemoryExtractionJobRepository,
)
from app.persistence.repositories.character_runtime import (
    DEFAULT_CHARACTER_STATE_VALUES,
    RunCharacterRepository,
)
from app.persistence.repositories.operations import ModelRunRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.services.memory import MemoryService
from app.services.memory_extraction import (
    MAX_ATTEMPTS,
    MemoryExtractionStatusService,
    MemoryExtractionWorker,
)
from app.services.character_model import CHARACTER_STATE_SCHEMA_VERSION
from app.services.character_state_transitions import (
    CharacterStateTransitionService,
)


NOW = datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-11-17T08:00:00Z"


def memory_output(*, quote="I felt worried about the meeting."):
    return {
        "schema_version": "0.2",
        "proposals": [
            {
                "memory_scope": "episodic",
                "proposal": {
                    "proposal_id": "untrusted-proposal-id",
                    "memory_type": "reported_experience",
                    "information_class": "explicit_disclosure",
                    "content": "The client felt worried about the meeting.",
                    "evidence": [
                        {
                            "message_id": "patient-2",
                            "exact_quote": quote,
                        }
                    ],
                    "confidence": 0.8,
                    "status": "candidate",
                },
            }
        ],
        "events": [],
        "state_transitions": [],
    }


def dynamics_event():
    return {
        "proposal_id": "untrusted-event-id",
        "event_type": "emotional_reaction",
        "actor": "patient",
        "summary": "The client reports worry about the meeting.",
        "observed_fact": "The client says they felt worried.",
        "interpretation": "The meeting may be emotionally salient.",
        "psychological_dimensions": ["arousal", "social_evaluative_threat"],
        "evidence": [
            {
                "message_id": "patient-2",
                "exact_quote": "I felt worried about the meeting.",
            }
        ],
        "confidence": 0.8,
        "status": "candidate",
    }


def add_character_state_snapshot(manager):
    with manager.transaction("operational") as connection:
        RunCharacterRepository(connection).create_state_snapshot(
            snapshot_id="character-state-initial",
            run_id="run-1",
            state_schema_version=CHARACTER_STATE_SCHEMA_VERSION,
            snapshot_reason="initial",
            created_at=NOW_TEXT,
            values=DEFAULT_CHARACTER_STATE_VALUES,
        )
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET character_state_snapshot_id = 'character-state-initial'
            WHERE job_id = 'job-1'
            """
        )


class FakeMemoryClient:
    def __init__(self, content=None, error=None):
        self.config = Settings.from_environment(
            {"OLLAMA_MODEL": "memory-test-model"}
        ).get_provider("ollama")
        self.content = content or json.dumps(
            memory_output(),
            ensure_ascii=False,
        )
        self.error = error
        self.calls = []
        self.on_call = None

    def chat(self, model, messages, temperature=None, max_tokens=None):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.on_call is not None:
            self.on_call()
        if self.error is not None:
            raise self.error
        return {
            "content": self.content,
            "model": model,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


@pytest.fixture
def extraction_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "memory-extraction")
    manager.initialize()
    with manager.transaction("operational") as connection:
        CaseRepository(connection).create_case(
            case_id="case-1",
            case_code="CASE-001",
            display_name="Ava",
            status="active",
            created_at=NOW_TEXT,
            updated_at=NOW_TEXT,
        )
        CaseRepository(connection).create_case_version(
            case_version_id="version-1",
            case_id="case-1",
            version_number="1.0",
            modality="ACT",
            language="en",
            schema_version="0.2",
            created_at=NOW_TEXT,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="en",
            configuration_version="0.1",
            created_at=NOW_TEXT,
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
        messages = MessageRepository(connection)
        messages.create_message(
            message_id="therapist-previous",
            session_id="session-1",
            sequence_number=1,
            role="therapist",
            content="Earlier therapist turn.",
            created_at=NOW_TEXT,
        )
        messages.create_message(
            message_id="patient-previous",
            session_id="session-1",
            sequence_number=2,
            role="patient",
            content="Earlier disclosure should not be in this job.",
            created_at=NOW_TEXT,
        )
        messages.create_message(
            message_id="therapist-1",
            session_id="session-1",
            sequence_number=3,
            role="therapist",
            content="What happened at the meeting?",
            created_at=NOW_TEXT,
        )
        messages.create_message(
            message_id="patient-2",
            session_id="session-1",
            sequence_number=4,
            role="patient",
            content="I felt worried about the meeting.",
            created_at=NOW_TEXT,
        )
        messages.create_message(
            message_id="therapist-2",
            session_id="session-1",
            sequence_number=5,
            role="therapist",
            content="Tell me more.",
            created_at=NOW_TEXT,
        )
        messages.create_message(
            message_id="patient-future",
            session_id="session-1",
            sequence_number=6,
            role="patient",
            content="Future disclosure must not enter this job.",
            created_at=NOW_TEXT,
        )
        connection.execute(
            """
            INSERT INTO interaction_requests (
                request_id, session_id, idempotency_key, request_hash,
                therapist_message_id, patient_message_id, processing_status,
                created_at, completed_at
            )
            VALUES (
                'request-1', 'session-1', 'key-1', 'hash-1',
                'therapist-1', 'patient-2', 'completed', ?, ?
            )
            """,
            (NOW_TEXT, NOW_TEXT),
        )
        MemoryExtractionJobRepository(connection).enqueue(
            job_id="job-1",
            run_id="run-1",
            session_id="session-1",
            interaction_request_id="request-1",
            created_at=NOW_TEXT,
        )

    clock = [NOW]
    client = FakeMemoryClient()
    agent = MemoryExtractionAgent(client, max_tokens=256)
    memory_service = MemoryService(manager)
    worker = MemoryExtractionWorker(
        manager,
        memory_service,
        agent,
        request_timeout_seconds=2,
        poll_interval_seconds=0.1,
        id_factory=lambda: "worker-test",
        clock=lambda: clock[0],
    )
    return {
        "manager": manager,
        "client": client,
        "service": memory_service,
        "worker": worker,
        "clock": clock,
    }


def test_agent_uses_only_provided_transcript_and_validates_output():
    client = FakeMemoryClient()
    agent = MemoryExtractionAgent(client)

    output = agent.extract(
        interaction_request_id="request-1",
        messages=[
            {
                "message_id": "patient-2",
                "role": "patient",
                "content": "I felt worried about the meeting.",
            }
        ],
    )

    assert len(output.proposals) == 1
    assert client.calls[0]["temperature"] == 0.0
    agent_input = json.loads(client.calls[0]["messages"][1]["content"])
    assert "hidden_case_fact" not in agent_input["messages"][0]["content"]
    schema_properties = agent_input["expected_output_schema"]["properties"]
    assert set(schema_properties) == {
        "schema_version",
        "proposals",
        "events",
        "state_transitions",
    }

    invalid_client = FakeMemoryClient(content='{"proposals": []}')
    with pytest.raises(MemoryExtractionAgentError):
        MemoryExtractionAgent(invalid_client).extract(
            interaction_request_id="request-1",
            messages=[
                {
                    "message_id": "patient-2",
                    "role": "patient",
                    "content": "I felt worried.",
                }
            ],
        )


def test_worker_persists_review_pending_memory_and_respects_as_of_transcript(
    extraction_system,
):
    system = extraction_system

    def assert_no_write_transaction_is_open():
        with system["manager"].connection("operational") as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()

    system["client"].on_call = assert_no_write_transaction_is_open

    assert system["worker"].process_one() is True
    assert system["worker"].process_one() is False

    call = system["client"].calls[0]
    transcript = json.loads(call["messages"][1]["content"])["messages"]
    assert [message["message_id"] for message in transcript] == [
        "therapist-1",
        "patient-2",
    ]
    assert "Earlier disclosure" not in call["messages"][1]["content"]
    assert "Future disclosure" not in call["messages"][1]["content"]

    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "completed"
    assert job.attempt_count == 1
    assert job.candidate_count == 1

    with system["manager"].connection("operational") as connection:
        model_run = connection.execute(
            """
            SELECT run_id, session_id, component, execution_status,
                   output_validation_status, input_hash, output_hash,
                   prompt_id, prompt_version, input_schema_version,
                   output_schema_version, generation_parameters
            FROM model_runs
            WHERE component = 'memory_extraction_agent'
            """
        ).fetchone()
        extraction_job = connection.execute(
            """
            SELECT output_hash
            FROM memory_extraction_jobs
            WHERE job_id = 'job-1'
            """
        ).fetchone()
    assert model_run is not None
    assert model_run["run_id"] == "run-1"
    assert model_run["session_id"] == "session-1"
    assert model_run["execution_status"] == "completed"
    assert model_run["output_validation_status"] == "valid"
    assert model_run["input_hash"].startswith("sha256:")
    assert model_run["output_hash"] == extraction_job["output_hash"]
    assert model_run["prompt_id"] == "MEMORY_EXTRACTION_PROMPT_V0"
    assert model_run["prompt_version"] == "0.2"
    assert model_run["input_schema_version"] == "0.2"
    assert model_run["output_schema_version"] == "0.2"
    assert json.loads(model_run["generation_parameters"]) == {
        "temperature": 0.0,
        "max_tokens": 256,
    }

    memories = system["service"].list_memories(
        "run-1",
        status="requires_review",
    )
    assert len(memories) == 1
    assert memories[0].status == "requires_review"
    assert memories[0].source_session_id == "session-1"
    evidence = system["service"].list_evidence(memories[0].memory_id)
    assert evidence[0].excerpt == "I felt worried about the meeting."


def test_worker_completes_without_forcing_a_memory_candidate(
    extraction_system,
):
    system = extraction_system
    system["client"].content = json.dumps(
        {
            "schema_version": "0.2",
            "proposals": [],
            "events": [],
            "state_transitions": [],
        }
    )

    assert system["worker"].process_one() is True
    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")

    assert job is not None
    assert job.status == "completed"
    assert job.candidate_count == 0
    assert system["service"].list_memories("run-1") == []


def test_worker_persists_event_as_unverified_with_exact_source_span(
    extraction_system,
):
    system = extraction_system
    payload = memory_output()
    payload["events"] = [dynamics_event()]
    system["client"].content = json.dumps(payload, ensure_ascii=False)

    assert system["worker"].process_one() is True

    with system["manager"].connection("operational") as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE extraction_method = 'model_assisted'"
        ).fetchone()
        evidence = connection.execute(
            "SELECT * FROM event_evidence WHERE event_id = ?",
            (event["event_id"],),
        ).fetchone()
    assert event["event_status"] == "requires_review"
    assert event["actor"] == "patient"
    assert event["extractor_version"] == "character-dynamics-extraction-v0.2"
    event_payload = json.loads(event["payload"])
    assert event_payload["observed_fact"] == "The client says they felt worried."
    assert event_payload["interpretation"] == (
        "The meeting may be emotionally salient."
    )
    assert evidence["message_id"] == "patient-2"
    assert evidence["start_offset"] == 0
    assert evidence["end_offset"] == len(
        "I felt worried about the meeting."
    )


def test_worker_creates_review_only_state_transition_then_applies_once(
    extraction_system,
):
    system = extraction_system
    add_character_state_snapshot(system["manager"])
    payload = memory_output()
    payload["state_transitions"] = [
        {
            "proposal_id": "untrusted-transition-id",
            "run_id": "run-1",
            "session_id": "session-1",
            "variable_name": "perceived_safety",
            "previous_value": 2,
            "proposed_value": 1,
            "evidence_message_ids": ["patient-2"],
            "evidence": [
                {
                    "message_id": "patient-2",
                    "exact_quote": "I felt worried about the meeting.",
                }
            ],
            "rationale": "The client reports worry in this situation.",
            "confidence": 0.6,
            "status": "candidate",
        }
    ]
    system["client"].content = json.dumps(payload, ensure_ascii=False)

    assert system["worker"].process_one() is True
    with system["manager"].connection("operational") as connection:
        transition = connection.execute(
            "SELECT * FROM character_state_transitions"
        ).fetchone()
        before_values = RunCharacterRepository(
            connection
        ).get_state_snapshot_values("character-state-initial")

    assert transition["validation_status"] == "requires_review"
    assert transition["idempotency_key"] == (
        "character-dynamics:request-1:state:0"
    )
    assert before_values["perceived_safety"] == 2

    service = CharacterStateTransitionService(system["manager"])
    accepted = service.accept_transition(
        transition["transition_id"],
        validated_at=NOW_TEXT,
    )
    repeated = service.accept_transition(
        transition["transition_id"],
        validated_at=NOW_TEXT,
    )
    assert accepted["validation_status"] == "accepted"
    assert repeated["accepted_value"] == 1
    with system["manager"].connection("operational") as connection:
        snapshots = connection.execute(
            "SELECT COUNT(*) FROM character_state_snapshots "
            "WHERE run_id = 'run-1'"
        ).fetchone()[0]
        current = RunCharacterRepository(
            connection
        ).get_current_state_snapshot("run-1")
        current_values = RunCharacterRepository(
            connection
        ).get_state_snapshot_values(current["snapshot_id"])
    assert snapshots == 2
    assert current_values["perceived_safety"] == 1


def test_extraction_uses_state_snapshot_pinned_at_interaction_time(
    extraction_system,
):
    system = extraction_system
    add_character_state_snapshot(system["manager"])
    future_values = dict(DEFAULT_CHARACTER_STATE_VALUES)
    future_values["perceived_safety"] = 4
    with system["manager"].transaction("operational") as connection:
        RunCharacterRepository(connection).create_state_snapshot(
            snapshot_id="character-state-future",
            run_id="run-1",
            session_id="session-1",
            previous_snapshot_id="character-state-initial",
            state_schema_version=CHARACTER_STATE_SCHEMA_VERSION,
            snapshot_reason="reviewed_transition",
            created_at="2026-11-17T08:01:00Z",
            values=future_values,
        )

    assert system["worker"].process_one() is True

    agent_input = json.loads(
        system["client"].calls[0]["messages"][1]["content"]
    )
    assert agent_input["character_state_snapshot_id"] == (
        "character-state-initial"
    )
    assert agent_input["current_character_state"]["perceived_safety"] == 2


def test_worker_replays_legacy_saved_memory_output(extraction_system):
    system = extraction_system
    legacy_output = memory_output()
    legacy_output["schema_version"] = "0.1"
    legacy_output.pop("events")
    legacy_output.pop("state_transitions")
    serialized = json.dumps(legacy_output, ensure_ascii=False)
    with system["manager"].transaction("operational") as connection:
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET proposal_payload = ?, output_hash = ?
            WHERE job_id = 'job-1'
            """,
            (
                serialized,
                system["worker"]._digest_text(serialized),
            ),
        )

    assert system["worker"].process_one() is True
    assert system["client"].calls == []
    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "completed"
    assert len(system["service"].list_memories("run-1")) == 1


def test_worker_rejects_nonexistent_character_event_quote(
    extraction_system,
):
    system = extraction_system
    event = dynamics_event()
    event["evidence"][0]["exact_quote"] = "This was never said."
    payload = memory_output()
    payload["events"] = [event]
    system["client"].content = json.dumps(payload, ensure_ascii=False)

    assert system["worker"].process_one() is True

    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "failed"
    assert job.last_error_code == "invalid_character_dynamics_evidence"
    with system["manager"].connection("operational") as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE extraction_method = 'model_assisted'"
        ).fetchone()[0]
    assert count == 0


def test_worker_records_invalid_model_output_as_failed_execution(
    extraction_system,
):
    system = extraction_system
    system["client"].content = '{"schema_version":"invalid","proposals":[]}'

    assert system["worker"].process_one() is True

    with system["manager"].connection("operational") as connection:
        model_run = connection.execute(
            """
            SELECT execution_status, output_validation_status, output_hash
            FROM model_runs
            WHERE component = 'memory_extraction_agent'
            """
        ).fetchone()
        job = connection.execute(
            "SELECT status, last_error_code FROM memory_extraction_jobs "
            "WHERE job_id = 'job-1'"
        ).fetchone()
    assert model_run["execution_status"] == "failed"
    assert model_run["output_validation_status"] == "invalid"
    assert model_run["output_hash"] is None
    assert job["status"] == "pending"
    assert job["last_error_code"] == "invalid_memory_extraction_output"


def test_worker_marks_invalid_evidence_as_terminal_failure(
    extraction_system,
):
    system = extraction_system
    system["client"].content = json.dumps(
        memory_output(quote="This exact quote is not in the transcript."),
        ensure_ascii=False,
    )

    assert system["worker"].process_one() is True

    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "failed"
    assert job.attempt_count == 1
    assert job.last_error_code == "invalid_memory_evidence"
    assert system["service"].list_memories("run-1") == []


def test_worker_retries_transient_provider_failures(
    extraction_system,
):
    system = extraction_system
    system["client"].error = ProviderConnectionError("private connection detail")

    for attempt in range(MAX_ATTEMPTS):
        assert system["worker"].process_one() is True
        if attempt + 1 < MAX_ATTEMPTS:
            system["clock"][0] += timedelta(seconds=10)

    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "failed"
    assert job.attempt_count == MAX_ATTEMPTS
    assert job.last_error_code == "provider_unavailable"
    assert len(system["client"].calls) == MAX_ATTEMPTS
    with system["manager"].connection("operational") as connection:
        executions = connection.execute(
            """
            SELECT execution_status, output_validation_status
            FROM model_runs
            WHERE component = 'memory_extraction_agent'
            ORDER BY started_at, model_run_id
            """
        ).fetchall()
    assert len(executions) == MAX_ATTEMPTS
    assert all(row["execution_status"] == "failed" for row in executions)
    assert all(
        row["output_validation_status"] == "not_validated"
        for row in executions
    )


def test_worker_rejects_therapist_authored_quotes_for_automatic_memory(
    extraction_system,
):
    system = extraction_system
    proposal = memory_output()["proposals"][0]["proposal"]
    proposal["information_class"] = "system_generated_summary"
    proposal["evidence"] = [
        {
            "message_id": "therapist-1",
            "exact_quote": "What happened at the meeting?",
        }
    ]
    system["client"].content = json.dumps(
        {
            "schema_version": "0.2",
            "proposals": [
                {"memory_scope": "therapeutic", "proposal": proposal}
            ],
            "events": [],
            "state_transitions": [],
        },
        ensure_ascii=False,
    )

    assert system["worker"].process_one() is True
    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")

    assert job is not None
    assert job.status == "failed"
    assert job.last_error_code == "invalid_memory_evidence"
    assert system["service"].list_memories("run-1") == []


def test_worker_reuses_saved_proposals_after_a_partial_attempt(
    extraction_system,
):
    system = extraction_system
    payload = memory_output()
    payload["events"] = [dynamics_event()]
    system["client"].content = json.dumps(payload, ensure_ascii=False)
    original_create_candidate = system["service"].create_candidate

    def fail_candidate_creation(**kwargs):
        raise RuntimeError("temporary persistence interruption")

    system["service"].create_candidate = fail_candidate_creation
    assert system["worker"].process_one() is True
    assert len(system["client"].calls) == 1

    with system["manager"].connection("operational") as connection:
        saved = connection.execute(
            """
            SELECT proposal_payload, output_hash, status
            FROM memory_extraction_jobs
            WHERE job_id = 'job-1'
            """
        ).fetchone()
    assert saved["proposal_payload"] is not None
    assert saved["output_hash"].startswith("sha256:")
    assert saved["status"] == "pending"
    with system["manager"].connection("operational") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE extraction_method = 'model_assisted'"
        ).fetchone()[0] == 1

    system["service"].create_candidate = original_create_candidate
    system["clock"][0] += timedelta(seconds=10)
    system["worker"] = MemoryExtractionWorker(
        system["manager"],
        system["service"],
        MemoryExtractionAgent(system["client"]),
        request_timeout_seconds=2,
        poll_interval_seconds=0.1,
        id_factory=lambda: "worker-restarted",
        clock=lambda: system["clock"][0],
    )
    assert system["worker"].process_one() is True
    assert len(system["client"].calls) == 1
    with system["manager"].connection("operational") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE extraction_method = 'model_assisted'"
        ).fetchone()[0] == 1

    job = MemoryExtractionStatusService(
        system["manager"]
    ).get_job("run-1", "request-1")
    assert job is not None
    assert job.status == "completed"
    assert job.attempt_count == 2
    assert job.candidate_count == 1
    with system["manager"].connection("operational") as connection:
        assert connection.execute(
            """
            SELECT COUNT(*) FROM model_runs
            WHERE component = 'memory_extraction_agent'
            """
        ).fetchone()[0] == 1


def test_outbox_recovers_expired_lease_and_rejects_stale_owner(
    extraction_system,
):
    manager = extraction_system["manager"]
    first_lease_end = "2026-11-17T08:00:32Z"
    with manager.transaction("operational") as connection:
        repository = MemoryExtractionJobRepository(connection)
        first = repository.claim_next(
            worker_id="worker-a",
            now=NOW_TEXT,
            lease_expires_at=first_lease_end,
            max_attempts=MAX_ATTEMPTS,
        )
        assert first is not None
        assert first["attempt_count"] == 1

    with manager.transaction("operational") as connection:
        repository = MemoryExtractionJobRepository(connection)
        assert repository.claim_next(
            worker_id="worker-b",
            now="2026-11-17T08:00:10Z",
            lease_expires_at="2026-11-17T08:00:42Z",
            max_attempts=MAX_ATTEMPTS,
        ) is None

    with manager.transaction("operational") as connection:
        repository = MemoryExtractionJobRepository(connection)
        second = repository.claim_next(
            worker_id="worker-b",
            now=first_lease_end,
            lease_expires_at="2026-11-17T08:01:02Z",
            max_attempts=MAX_ATTEMPTS,
        )
        assert second is not None
        assert second["attempt_count"] == 2
        assert repository.save_proposals(
            "job-1",
            worker_id="worker-b",
            proposal_payload=(
                '{"schema_version":"0.2","proposals":[],"events":[],'
                '"state_transitions":[]}'
            ),
            output_hash="sha256:test",
            updated_at=first_lease_end,
        ) is True
        assert repository.mark_completed(
            "job-1",
            worker_id="worker-a",
            candidate_count=0,
            completed_at=first_lease_end,
        ) is False
        assert repository.mark_completed(
            "job-1",
            worker_id="worker-b",
            candidate_count=0,
            completed_at=first_lease_end,
        ) is True


def test_exhausted_worker_lease_closes_linked_model_run(extraction_system):
    manager = extraction_system["manager"]
    with manager.transaction("operational") as connection:
        jobs = MemoryExtractionJobRepository(connection)
        claimed = jobs.claim_next(
            worker_id="worker-crashed",
            now=NOW_TEXT,
            lease_expires_at="2026-11-17T08:00:02Z",
            max_attempts=MAX_ATTEMPTS,
        )
        assert claimed is not None
        ModelRunRepository(connection).create_model_run(
            model_run_id="model-run-abandoned",
            run_id="run-1",
            session_id="session-1",
            component="memory_extraction_agent",
            provider="ollama",
            model_identifier="memory-test-model",
            execution_status="in_progress",
            started_at=NOW_TEXT,
            generation_parameters={},
        )
        assert jobs.set_model_run(
            "job-1",
            worker_id="worker-crashed",
            model_run_id="model-run-abandoned",
            updated_at=NOW_TEXT,
        )
        connection.execute(
            """
            UPDATE memory_extraction_jobs
            SET attempt_count = ?, lease_expires_at = ?
            WHERE job_id = 'job-1'
            """,
            (MAX_ATTEMPTS, "2026-11-17T08:00:02Z"),
        )

    with manager.transaction("operational") as connection:
        assert MemoryExtractionJobRepository(connection).claim_next(
            worker_id="worker-recovery",
            now="2026-11-17T08:00:03Z",
            lease_expires_at="2026-11-17T08:00:05Z",
            max_attempts=MAX_ATTEMPTS,
        ) is None
        model_run = ModelRunRepository(connection).get("model-run-abandoned")
        job = MemoryExtractionJobRepository(connection).get_by_interaction(
            "request-1"
        )

    assert model_run["execution_status"] == "failed"
    assert model_run["output_validation_status"] == "not_validated"
    assert job["status"] == "failed"


def test_extraction_status_endpoint_is_run_scoped(extraction_system):
    system = extraction_system

    class RunLookup:
        @staticmethod
        def get_run(run_id):
            return object() if run_id == "run-1" else None

    previous_status_service = app.dependency_overrides.get(
        get_memory_extraction_status_service
    )
    previous_run_service = app.dependency_overrides.get(get_run_service)
    app.dependency_overrides[get_memory_extraction_status_service] = (
        lambda: MemoryExtractionStatusService(system["manager"])
    )
    app.dependency_overrides[get_run_service] = lambda: RunLookup()
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/simulation-runs/run-1/memories/"
            "processing/request-1"
        )
        wrong_run = client.get(
            "/api/v1/simulation-runs/other-run/memories/"
            "processing/request-1"
        )
    finally:
        if previous_status_service is None:
            app.dependency_overrides.pop(
                get_memory_extraction_status_service,
                None,
            )
        else:
            app.dependency_overrides[
                get_memory_extraction_status_service
            ] = previous_status_service
        if previous_run_service is None:
            app.dependency_overrides.pop(get_run_service, None)
        else:
            app.dependency_overrides[get_run_service] = previous_run_service

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["attempt_count"] == 0
    assert wrong_run.status_code == 404
