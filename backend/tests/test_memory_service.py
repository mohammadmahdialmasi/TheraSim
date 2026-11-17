import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.routes.memories import get_memory_service
from app.api.routes.runs import get_run_service
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.services.character_model import MemoryEvidenceQuote, MemoryProposal
from app.services.memory import (
    MemoryEvidenceValidationError,
    MemoryIdempotencyConflictError,
    MemoryRequestNotCompletedError,
    MemoryReviewConflictError,
    MemoryService,
)


NOW = "2026-11-17T10:00:00Z"


@pytest.fixture
def memory_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "memory-service")
    manager.initialize()

    with manager.transaction("operational") as connection:
        cases = CaseRepository(connection)
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
        sessions = SessionRepository(connection)
        sessions.create_session(
            session_id="session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )
        messages = MessageRepository(connection)
        messages.create_message(
            message_id="patient-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content="I stayed quiet and felt embarrassed.",
            created_at=NOW,
        )
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
        messages.create_message(
            message_id="therapist-2",
            session_id="session-2",
            sequence_number=1,
            role="therapist",
            content="What did you notice?",
            created_at=NOW,
        )
        messages.create_message(
            message_id="patient-2",
            session_id="session-2",
            sequence_number=2,
            role="patient",
            content="I noticed I was avoiding the meeting again.",
            created_at=NOW,
        )
        connection.execute(
            """
            INSERT INTO interaction_requests (
                request_id, session_id, idempotency_key, request_hash,
                therapist_message_id, patient_message_id, processing_status,
                created_at, completed_at
            )
            VALUES (
                'request-2', 'session-2', 'key-2', 'hash-2',
                'therapist-2', 'patient-2', 'completed', ?, ?
            )
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO interaction_requests (
                request_id, session_id, idempotency_key, request_hash,
                therapist_message_id, processing_status, created_at
            )
            VALUES (
                'request-pending', 'session-2', 'key-pending',
                'hash-pending', 'therapist-2', 'in_progress', ?
            )
            """,
            (NOW,),
        )

    ids = iter(range(1, 100))
    return {
        "manager": manager,
        "service": MemoryService(
            manager,
            id_factory=lambda: f"generated-{next(ids)}",
        ),
    }


def proposal(content="Ava described avoiding the meeting."):
    return MemoryProposal(
        proposal_id="untrusted-model-proposal-id",
        memory_type="avoidance_report",
        information_class="explicit_disclosure",
        content=content,
        evidence=(
            MemoryEvidenceQuote(
                message_id="patient-1",
                exact_quote="I stayed quiet and felt embarrassed.",
            ),
            MemoryEvidenceQuote(
                message_id="patient-2",
                exact_quote="I noticed I was avoiding the meeting again.",
            ),
        ),
        confidence=0.85,
    )


def create_candidate(system, *, proposal_index=0, content=None, supersedes=None):
    selected_proposal = proposal(
        content if content is not None else "Ava described avoiding the meeting."
    )
    return system["service"].create_candidate(
        run_id="run-1",
        session_id="session-2",
        interaction_request_id="request-2",
        proposal_index=proposal_index,
        memory_scope="episodic",
        proposal=selected_proposal,
        created_at=NOW,
        supersedes_memory_id=supersedes,
    )


def test_candidate_requires_review_and_is_idempotent(memory_system):
    first = create_candidate(memory_system)
    retry = create_candidate(memory_system)

    assert first.memory_id == retry.memory_id
    assert first.status == "requires_review"
    assert first.memory_version == 1
    assert first.source_session_id == "session-2"

    with memory_system["manager"].connection("operational") as connection:
        evidence = connection.execute(
            """
            SELECT message_id, start_offset, end_offset
            FROM memory_evidence
            WHERE memory_id = ?
            ORDER BY message_id
            """,
            (first.memory_id,),
        ).fetchall()
        reviews = connection.execute(
            "SELECT COUNT(*) FROM memory_reviews"
        ).fetchone()[0]

    assert [(row["message_id"], row["start_offset"], row["end_offset"]) for row in evidence] == [
        ("patient-1", 0, 36),
        ("patient-2", 0, 43),
    ]
    assert reviews == 0

    with pytest.raises(MemoryIdempotencyConflictError):
        create_candidate(
            memory_system,
            content="Different candidate content.",
        )


def test_rejecting_candidate_keeps_it_out_of_active_memory(memory_system):
    candidate = create_candidate(memory_system)

    rejected, review = memory_system["service"].review_candidate(
        candidate.memory_id,
        decision="rejected",
        reviewer_id="local-reviewer",
        rationale="The candidate combines evidence too broadly.",
        reviewed_at=NOW,
    )

    assert rejected.status == "rejected"
    assert review.decision == "rejected"
    assert memory_system["service"].list_memories(
        "run-1",
        status="active",
    ) == []

    retried, same_review = memory_system["service"].review_candidate(
        candidate.memory_id,
        decision="rejected",
        reviewer_id="local-reviewer",
        rationale="The candidate combines evidence too broadly.",
        reviewed_at=NOW,
    )
    assert retried == rejected
    assert same_review == review

    with pytest.raises(MemoryReviewConflictError):
        memory_system["service"].review_candidate(
            candidate.memory_id,
            decision="accepted",
            reviewer_id="local-reviewer",
            rationale="Conflicting decision.",
            reviewed_at=NOW,
        )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="memory_reviews_are_immutable",
    ):
        with memory_system["manager"].transaction("operational") as connection:
            connection.execute(
                """
                UPDATE memory_reviews
                SET rationale = 'changed'
                WHERE memory_id = ?
                """,
                (candidate.memory_id,),
            )


def test_accepted_revision_supersedes_prior_memory_and_preserves_lineage(
    memory_system,
):
    original = create_candidate(memory_system)
    active, _ = memory_system["service"].review_candidate(
        original.memory_id,
        decision="accepted",
        reviewer_id="local-reviewer",
        rationale="Evidence supports the memory.",
        reviewed_at=NOW,
    )
    revision = create_candidate(
        memory_system,
        proposal_index=1,
        content="Ava reported avoiding a meeting again.",
        supersedes=active.memory_id,
    )

    revised, review = memory_system["service"].review_candidate(
        revision.memory_id,
        decision="accepted",
        reviewer_id="local-reviewer",
        rationale="The updated wording is more precise.",
        reviewed_at=NOW,
    )
    old = next(
        item
        for item in memory_system["service"].list_memories("run-1")
        if item.memory_id == active.memory_id
    )

    assert revised.status == "active"
    assert revised.memory_version == 2
    assert revised.supersedes_memory_id == active.memory_id
    assert review.decision == "accepted"
    assert old.status == "superseded"


def test_candidate_rejects_unavailable_or_nonmatching_evidence(memory_system):
    invalid = MemoryProposal(
        proposal_id="untrusted-id",
        memory_type="avoidance_report",
        information_class="explicit_disclosure",
        content="Ava disclosed a fact.",
        evidence=(
            MemoryEvidenceQuote(
                message_id="patient-1",
                exact_quote="This quote is not in the transcript.",
            ),
        ),
        confidence=0.7,
    )

    with pytest.raises(MemoryEvidenceValidationError):
        memory_system["service"].create_candidate(
            run_id="run-1",
            session_id="session-2",
            interaction_request_id="request-2",
            proposal_index=0,
            memory_scope="episodic",
            proposal=invalid,
            created_at=NOW,
        )

    with pytest.raises(MemoryRequestNotCompletedError):
        memory_system["service"].create_candidate(
            run_id="run-1",
            session_id="session-2",
            interaction_request_id="request-pending",
            proposal_index=0,
            memory_scope="episodic",
            proposal=proposal(),
            created_at=NOW,
        )

    assert memory_system["service"].list_memories("run-1") == []


def test_candidate_rejects_cross_run_and_future_evidence(memory_system):
    manager = memory_system["manager"]
    with manager.transaction("operational") as connection:
        cases = CaseRepository(connection)
        cases.create_case(
            case_id="case-2",
            case_code="CASE-002",
            display_name="Other client",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        cases.create_case_version(
            case_version_id="version-2",
            case_id="case-2",
            version_number="1.0",
            modality="ACT",
            language="fa",
            schema_version="0.2",
            created_at=NOW,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-2",
            case_id="case-2",
            case_version_id="version-2",
            modality="ACT",
            language="fa",
            configuration_version="0.1",
            created_at=NOW,
            status="active",
        )
        SessionRepository(connection).create_session(
            session_id="session-other-run",
            run_id="run-2",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="patient-other-run",
            session_id="session-other-run",
            sequence_number=1,
            role="patient",
            content="A different client's statement.",
            created_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="patient-future",
            session_id="session-2",
            sequence_number=3,
            role="patient",
            content="This message occurred after the interaction response.",
            created_at=NOW,
        )

    cross_run_proposal = MemoryProposal(
        proposal_id="cross-run",
        memory_type="reported_experience",
        information_class="explicit_disclosure",
        content="A purported disclosure.",
        evidence=(
            MemoryEvidenceQuote(
                message_id="patient-other-run",
                exact_quote="A different client's statement.",
            ),
        ),
        confidence=0.7,
    )
    future_proposal = MemoryProposal(
        proposal_id="future",
        memory_type="reported_experience",
        information_class="explicit_disclosure",
        content="A future statement.",
        evidence=(
            MemoryEvidenceQuote(
                message_id="patient-future",
                exact_quote="This message occurred after the interaction response.",
            ),
        ),
        confidence=0.7,
    )

    for selected_proposal, proposal_index in (
        (cross_run_proposal, 0),
        (future_proposal, 1),
    ):
        with pytest.raises(MemoryEvidenceValidationError):
            memory_system["service"].create_candidate(
                run_id="run-1",
                session_id="session-2",
                interaction_request_id="request-2",
                proposal_index=proposal_index,
                memory_scope="episodic",
                proposal=selected_proposal,
                created_at=NOW,
            )

    assert memory_system["service"].list_memories("run-1") == []


@pytest.fixture
def memory_api(memory_system):
    class RunLookup:
        @staticmethod
        def get_run(run_id):
            return object() if run_id == "run-1" else None

    previous_memory_service = app.dependency_overrides.get(
        get_memory_service
    )
    previous_run_service = app.dependency_overrides.get(get_run_service)
    app.dependency_overrides[get_memory_service] = (
        lambda: memory_system["service"]
    )
    app.dependency_overrides[get_run_service] = lambda: RunLookup()
    yield TestClient(app)
    if previous_memory_service is None:
        app.dependency_overrides.pop(get_memory_service, None)
    else:
        app.dependency_overrides[get_memory_service] = previous_memory_service
    if previous_run_service is None:
        app.dependency_overrides.pop(get_run_service, None)
    else:
        app.dependency_overrides[get_run_service] = previous_run_service


def test_memory_api_creates_candidate_and_exposes_evidence(memory_api):
    response = memory_api.post(
        "/api/v1/simulation-runs/run-1/memories/candidates",
        json={
            "session_id": "session-2",
            "interaction_request_id": "request-2",
            "proposal_index": 0,
            "memory_scope": "episodic",
            "proposal": proposal().model_dump(),
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["status"] == "requires_review"
    assert [item["excerpt"] for item in body["evidence"]] == [
        "I stayed quiet and felt embarrassed.",
        "I noticed I was avoiding the meeting again.",
    ]

    listed = memory_api.get(
        "/api/v1/simulation-runs/run-1/memories",
        params={"status": "requires_review"},
    )
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_memory_api_rejects_invalid_evidence(memory_api):
    invalid_proposal = MemoryProposal(
        proposal_id="proposal",
        memory_type="avoidance_report",
        information_class="explicit_disclosure",
        content="Invalid quoted memory.",
        evidence=(
            MemoryEvidenceQuote(
                message_id="patient-1",
                exact_quote="Not present in the transcript.",
            ),
        ),
        confidence=0.7,
    )
    response = memory_api.post(
        "/api/v1/simulation-runs/run-1/memories/candidates",
        json={
            "session_id": "session-2",
            "interaction_request_id": "request-2",
            "proposal_index": 0,
            "memory_scope": "episodic",
            "proposal": invalid_proposal.model_dump(),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "memory_evidence_invalid"

    duplicate_evidence = proposal().model_dump()
    duplicate_evidence["evidence"] = [
        {
            "message_id": "patient-1",
            "exact_quote": "I stayed quiet",
        },
        {
            "message_id": "patient-1",
            "exact_quote": "felt embarrassed.",
        },
    ]
    duplicate = memory_api.post(
        "/api/v1/simulation-runs/run-1/memories/candidates",
        json={
            "session_id": "session-2",
            "interaction_request_id": "request-2",
            "proposal_index": 0,
            "memory_scope": "episodic",
            "proposal": duplicate_evidence,
        },
    )
    assert duplicate.status_code == 422


def test_memory_api_review_is_run_scoped_and_auditable(memory_api):
    created = memory_api.post(
        "/api/v1/simulation-runs/run-1/memories/candidates",
        json={
            "session_id": "session-2",
            "interaction_request_id": "request-2",
            "proposal_index": 0,
            "memory_scope": "episodic",
            "proposal": proposal().model_dump(),
        },
    )
    memory_id = created.json()["data"]["memory_id"]

    invalid_review = memory_api.post(
        f"/api/v1/simulation-runs/run-1/memories/{memory_id}/review",
        json={
            "decision": "accepted",
            "rationale": "   ",
        },
    )
    assert invalid_review.status_code == 422

    forged_reviewer = memory_api.post(
        f"/api/v1/simulation-runs/run-1/memories/{memory_id}/review",
        json={
            "decision": "accepted",
            "reviewer_id": "named-user",
            "rationale": "Evidence is adequate.",
        },
    )
    assert forged_reviewer.status_code == 422

    reviewed = memory_api.post(
        f"/api/v1/simulation-runs/run-1/memories/{memory_id}/review",
        json={
            "decision": "accepted",
            "rationale": "The cited client statements support this memory.",
        },
    )

    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "active"
    assert reviewed.json()["review"]["decision"] == "accepted"
    assert (
        reviewed.json()["review"]["reviewer_id"]
        == "unverified_local_caller"
    )
    assert reviewed.json()["review"]["rationale"].startswith(
        "The cited client statements"
    )

    wrong_run = memory_api.post(
        f"/api/v1/simulation-runs/other-run/memories/{memory_id}/review",
        json={
            "decision": "rejected",
            "rationale": "Wrong Run.",
        },
    )
    assert wrong_run.status_code == 404
