import json
import sqlite3
import uuid

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.simulation_runs import SimulationRunRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.disclosures import DisclosureRepository
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.state import StateRepository, STATE_VARIABLES
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.evaluations import EvaluationRepository
from app.persistence.repositories.operations import ModelRunRepository, AuditRepository


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "domain-repositories")
    result.initialize()
    return result


@pytest.fixture
def seeded(manager):
    token = uuid.uuid4().hex
    ids = {
        "case_id": f"case-{token}",
        "version_id": f"version-{token}",
        "run_id": f"run-{token}",
        "session_id": f"session-{token}",
        "therapist_message_id": f"therapist-{token}",
        "patient_message_id": f"patient-{token}",
    }

    with manager.transaction("operational") as connection:
        cases = CaseRepository(connection)
        cases.create_case(
            case_id=ids["case_id"],
            case_code=f"TEST-{token[:12]}",
            display_name="Synthetic Ava",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        cases.create_case_version(
            case_version_id=ids["version_id"],
            case_id=ids["case_id"],
            version_number="0.2",
            modality="ACT",
            language="fa",
            schema_version="0.2",
            created_at=NOW,
        )
        SimulationRunRepository(connection).create_run(
            run_id=ids["run_id"],
            case_id=ids["case_id"],
            case_version_id=ids["version_id"],
            modality="ACT",
            language="fa",
            configuration_version="0.1",
            created_at=NOW,
            status="active",
        )
        SessionRepository(connection).create_session(
            session_id=ids["session_id"],
            run_id=ids["run_id"],
            session_number=1,
            status="active",
            created_at=NOW,
        )
        messages = MessageRepository(connection)
        messages.create_message(
            message_id=ids["therapist_message_id"],
            session_id=ids["session_id"],
            sequence_number=1,
            role="therapist",
            content="Can you tell me what happened in the meeting?",
            created_at=NOW,
        )
        messages.create_message(
            message_id=ids["patient_message_id"],
            session_id=ids["session_id"],
            sequence_number=2,
            role="patient",
            content="I felt nervous when I tried to speak.",
            created_at=NOW,
        )

    return ids


def test_disclosure_repository_tracks_current_status_and_history(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = DisclosureRepository(connection)

        repo.create_disclosure(
            disclosure_id="disclosure-1",
            run_id=seeded["run_id"],
            case_id=seeded["case_id"],
            case_version_id=seeded["version_id"],
            case_fact_id="AVA-FACT-001",
            created_at="2026-11-16T12:00:00Z",
            operation_id="disclosure-init-1",
        )

        assert repo.update_status(
            "disclosure-1",
            "candidate_disclosed",
            operation_id="disclosure-candidate-1",
            created_at="2026-11-16T12:00:01Z",
            validation_method="patient_annotation",
            source_message_id=seeded["patient_message_id"],
            evidence_start_offset=0,
            evidence_end_offset=6,
        )

        assert repo.update_status(
            "disclosure-1",
            "confirmed_disclosed",
            operation_id="disclosure-confirmed-1",
            created_at="2026-11-16T12:00:02Z",
            validation_method="validated_evidence",
        )

        assert not repo.update_status(
            "disclosure-1",
            "confirmed_disclosed",
            operation_id="disclosure-confirmed-1",
            created_at="2026-11-16T12:00:02Z",
            validation_method="validated_evidence",
        )

        current = repo.get_by_fact(seeded["run_id"], "AVA-FACT-001")
        assert current["disclosure_status"] == "confirmed_disclosed"
        assert current["source_message_id"] == seeded["patient_message_id"]

        history = repo.list_history("disclosure-1")
        assert [row["new_status"] for row in history] == [
            "not_disclosed",
            "candidate_disclosed",
            "confirmed_disclosed",
        ]


def test_disclosure_rejects_therapist_source_and_invalid_offsets(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = DisclosureRepository(connection)

        with pytest.raises(ValueError):
            repo.create_disclosure(
                disclosure_id="disclosure-invalid",
                run_id=seeded["run_id"],
                case_id=seeded["case_id"],
                case_version_id=seeded["version_id"],
                case_fact_id="AVA-FACT-002",
                created_at=NOW,
                operation_id="disclosure-invalid-op",
                disclosure_status="confirmed_disclosed",
                source_message_id=seeded["therapist_message_id"],
            )

        with pytest.raises(ValueError):
            repo.create_disclosure(
                disclosure_id="disclosure-invalid-span",
                run_id=seeded["run_id"],
                case_id=seeded["case_id"],
                case_version_id=seeded["version_id"],
                case_fact_id="AVA-FACT-003",
                created_at=NOW,
                operation_id="disclosure-invalid-span-op",
                source_message_id=seeded["patient_message_id"],
                evidence_start_offset=0,
                evidence_end_offset=999,
            )


def test_event_repository_persists_events_and_evidence(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = EventRepository(connection)

        event_id = repo.create_event(
            event_id="event-1",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            sequence_number=1,
            event_type="patient_response_recorded",
            actor="application",
            payload={"source": "interaction"},
            extraction_method="application_rule",
            event_status="accepted",
            idempotency_key="event-key-1",
            created_at=NOW,
        )

        assert event_id == "event-1"
        assert repo.create_event(
            event_id="ignored-replay-id",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            sequence_number=9,
            event_type="patient_response_recorded",
            actor="application",
            payload={"source": "interaction"},
            extraction_method="application_rule",
            event_status="accepted",
            idempotency_key="event-key-1",
            created_at=NOW,
        ) == event_id

        assert repo.add_evidence(
            event_id=event_id,
            message_id=seeded["patient_message_id"],
            evidence_type="supporting",
            start_offset=0,
            end_offset=6,
        )

        assert not repo.add_evidence(
            event_id=event_id,
            message_id=seeded["patient_message_id"],
            evidence_type="supporting",
            start_offset=0,
            end_offset=6,
        )

        assert json.loads(repo.get(event_id)["payload"]) == {
            "source": "interaction"
        }
        assert len(repo.list_evidence(event_id)) == 1


def test_event_repository_rejects_cross_session_evidence(manager, seeded):
    with manager.transaction("operational") as connection:
        sessions = SessionRepository(connection)
        sessions.create_session(
            session_id="another-session",
            run_id=seeded["run_id"],
            session_number=2,
            status="initialized",
            created_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="another-session-message",
            session_id="another-session",
            sequence_number=1,
            role="patient",
            content="A different session.",
            created_at=NOW,
        )
        events = EventRepository(connection)
        events.create_event(
            event_id="session-one-event",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            sequence_number=1,
            event_type="test",
            actor="application",
            payload={},
            extraction_method="application_rule",
            event_status="accepted",
            idempotency_key="session-one-key",
            created_at=NOW,
        )

        with pytest.raises(ValueError):
            events.add_evidence(
                event_id="session-one-event",
                message_id="another-session-message",
                evidence_type="supporting",
            )


def test_state_repository_persists_snapshot_and_resolved_transition(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = StateRepository(connection)
        values = {name: 1 for name in STATE_VARIABLES}

        repo.create_snapshot(
            snapshot_id="snapshot-1",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            state_schema_version="0.1",
            snapshot_reason="initial",
            created_at=NOW,
            values=values,
        )

        repo.create_snapshot(
            snapshot_id="snapshot-2",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            previous_snapshot_id="snapshot-1",
            state_schema_version="0.1",
            snapshot_reason="accepted_transition",
            created_at=NOW,
            values={**values, "willingness": 2},
        )

        assert repo.get_snapshot_values("snapshot-1") == values
        assert repo.get_snapshot_values("snapshot-2")["willingness"] == 2

        repo.create_transition(
            transition_id="transition-1",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            variable_name="willingness",
            previous_value=1,
            proposed_value=2,
            validation_status="pending",
            idempotency_key="transition-key-1",
            created_at=NOW,
        )

        assert repo.resolve_transition(
            "transition-1",
            validation_status="accepted",
            accepted_value=2,
            resulting_snapshot_id="snapshot-2",
            validated_at=NOW,
        )

        assert not repo.resolve_transition(
            "transition-1",
            validation_status="accepted",
            accepted_value=2,
            resulting_snapshot_id="snapshot-2",
            validated_at=NOW,
        )

        assert repo.add_transition_evidence(
            "transition-1",
            seeded["patient_message_id"],
            evidence_role="supporting",
        )

        transition = repo.list_transitions(seeded["run_id"])[0]
        assert transition["validation_status"] == "accepted"
        assert transition["accepted_value"] == 2


def test_state_repository_rejects_invalid_variables_and_values(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = StateRepository(connection)

        with pytest.raises(ValueError):
            repo.create_snapshot(
                snapshot_id="bad-snapshot",
                run_id=seeded["run_id"],
                state_schema_version="0.1",
                snapshot_reason="invalid",
                created_at=NOW,
                values={"unknown_variable": 2},
            )

        with pytest.raises(ValueError):
            repo.create_snapshot(
                snapshot_id="bad-snapshot-2",
                run_id=seeded["run_id"],
                state_schema_version="0.1",
                snapshot_reason="invalid",
                created_at=NOW,
                values={"willingness": 5},
            )


def test_memory_repository_preserves_sources_and_validates_confidence(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = MemoryRepository(connection)

        repo.create_memory(
            memory_id="memory-1",
            run_id=seeded["run_id"],
            source_session_id=seeded["session_id"],
            memory_type="client_statement",
            information_class="explicit_disclosure",
            content="Ava reported feeling nervous during a meeting.",
            confidence=0.8,
            status="active",
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
        )

        assert repo.add_evidence(
            "memory-1",
            seeded["patient_message_id"],
            "source",
        )
        assert not repo.add_evidence(
            "memory-1",
            seeded["patient_message_id"],
            "source",
        )

        assert repo.get("memory-1")["information_class"] == "explicit_disclosure"
        assert len(repo.list_evidence("memory-1")) == 1

        with pytest.raises(ValueError):
            repo.create_memory(
                memory_id="memory-invalid",
                run_id=seeded["run_id"],
                memory_type="invalid",
                information_class="confirmed_fact",
                content="Invalid confidence",
                confidence=1.5,
                memory_version=1,
                created_at=NOW,
                updated_at=NOW,
            )


def test_evaluation_repository_stores_rubric_items_and_evidence(manager, seeded):
    with manager.transaction("operational") as connection:
        repo = EvaluationRepository(connection)

        repo.create_rubric_version(
            rubric_version_id="rubric-version-1",
            rubric_id="ACT_RUBRIC_V0",
            version_number="0.2",
            modality="ACT",
            language="fa",
            schema_version="0.1",
            rubric_definition={"ratings": ["0", "1", "2", "3", "NE"]},
            created_at=NOW,
        )

        repo.create_evaluation(
            evaluation_id="evaluation-1",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            evaluation_scope="session",
            rubric_version_id="rubric-version-1",
            transcript_manifest=[
                {
                    "session_id": seeded["session_id"],
                    "transcript_version": 1,
                    "content_hash": "sha256:test",
                }
            ],
            evaluation_revision=1,
            status="completed",
            created_at=NOW,
        )

        repo.create_item(
            evaluation_item_id="evaluation-item-1",
            evaluation_id="evaluation-1",
            competency_id="ACT_COMPETENCY_001",
            rating_code="2",
            justification="The therapist used an open question.",
            alternative_response="Could you tell me more?",
        )

        excerpt = "I felt nervous"
        assert repo.add_evidence(
            evaluation_item_id="evaluation-item-1",
            message_id=seeded["patient_message_id"],
            evidence_role="supporting",
            start_offset=0,
            end_offset=len(excerpt),
            evidence_excerpt=excerpt,
        )

        assert len(repo.list_items("evaluation-1")) == 1

        with pytest.raises(ValueError):
            repo.add_evidence(
                evaluation_item_id="evaluation-item-1",
                message_id=seeded["patient_message_id"],
                evidence_role="mismatch",
                start_offset=0,
                end_offset=4,
                evidence_excerpt="wrong",
            )


def test_evaluation_repository_rejects_evidence_from_another_session(manager, seeded):
    with manager.transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="evaluation-other-session",
            run_id=seeded["run_id"],
            session_number=2,
            status="initialized",
            created_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="evaluation-other-message",
            session_id="evaluation-other-session",
            sequence_number=1,
            role="patient",
            content="Other session text.",
            created_at=NOW,
        )

        repo = EvaluationRepository(connection)
        repo.create_rubric_version(
            rubric_version_id="rubric-session-check",
            rubric_id="ACT_RUBRIC_CHECK",
            version_number="0.1",
            modality="ACT",
            language="fa",
            schema_version="0.1",
            rubric_definition={},
            created_at=NOW,
        )
        repo.create_evaluation(
            evaluation_id="evaluation-session-check",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            evaluation_scope="session",
            rubric_version_id="rubric-session-check",
            transcript_manifest=[],
            evaluation_revision=1,
            status="pending",
            created_at=NOW,
        )
        repo.create_item(
            evaluation_item_id="evaluation-item-check",
            evaluation_id="evaluation-session-check",
            competency_id="ACT-1",
            rating_code="NE",
        )

        with pytest.raises(ValueError):
            repo.add_evidence(
                evaluation_item_id="evaluation-item-check",
                message_id="evaluation-other-message",
                evidence_role="supporting",
            )


def test_model_run_and_audit_repositories(manager, seeded):
    with manager.transaction("operational") as connection:
        models = ModelRunRepository(connection)
        models.create_model_run(
            model_run_id="patient-model-run",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            component="patient_agent",
            provider="ollama",
            model_identifier="local-test-model",
            model_version="test",
            execution_status="in_progress",
            generation_parameters={"temperature": 0.4},
            started_at=NOW,
        )

        assert models.set_input_hash(
            "patient-model-run",
            "sha256:input",
        )
        assert models.set_input_hash(
            "patient-model-run",
            "sha256:input",
        )
        assert not models.set_input_hash(
            "patient-model-run",
            "sha256:different-input",
        )

        assert models.complete(
            "patient-model-run",
            completed_at=NOW,
            output_hash="sha256:output",
            output_validation_status="valid",
        )

        model = models.get("patient-model-run")
        assert model["execution_status"] == "completed"
        assert json.loads(model["generation_parameters"]) == {
            "temperature": 0.4
        }

        audit = AuditRepository(connection)
        audit.record(
            audit_event_id="audit-1",
            component="orchestrator",
            operation_type="message_persisted",
            entity_type="message",
            entity_id=seeded["patient_message_id"],
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            operation_status="success",
            metadata={"synthetic": True},
            created_at=NOW,
        )

        rows = audit.list_for_entity(
            "message",
            seeded["patient_message_id"],
        )
        assert len(rows) == 1
        assert json.loads(rows[0]["metadata"]) == {"synthetic": True}


def test_repositories_never_commit_the_callers_transaction(manager, seeded):
    with manager.connection("operational") as connection:
        repo = EventRepository(connection)
        connection.execute("BEGIN")

        repo.create_event(
            event_id="rollback-event",
            run_id=seeded["run_id"],
            session_id=seeded["session_id"],
            sequence_number=1,
            event_type="test",
            actor="application",
            payload={},
            extraction_method="application_rule",
            event_status="accepted",
            idempotency_key="rollback-key",
            created_at=NOW,
        )

        assert connection.in_transaction
        connection.rollback()

        assert repo.get("rollback-event") is None
