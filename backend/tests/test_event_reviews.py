import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.routes.events import (
    get_event_review_service,
)
from app.api.routes.runs import get_run_service
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.services.event_reviews import (
    EventReviewConflictError,
    EventReviewService,
)
from app.services.runs import RunService


NOW = "2026-11-17T08:00:00Z"
SOURCE_TEXT = "I felt worried about the meeting."


@pytest.fixture
def event_review_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "event-review")
    manager.initialize()
    with manager.transaction("operational") as connection:
        CaseRepository(connection).create_case(
            case_id="case-1",
            case_code="CASE-001",
            display_name="Ava",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        CaseRepository(connection).create_case_version(
            case_version_id="version-1",
            case_id="case-1",
            version_number="1.0",
            modality="ACT",
            language="en",
            schema_version="0.2",
            created_at=NOW,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="en",
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
            started_at=NOW,
        )
        MessageRepository(connection).create_message(
            message_id="patient-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content=SOURCE_TEXT,
            created_at=NOW,
        )
        events = EventRepository(connection)
        event_id = events.create_event(
            event_id="event-1",
            run_id="run-1",
            session_id="session-1",
            sequence_number=1,
            event_type="emotional_reaction",
            actor="patient",
            payload={
                "summary": "The client reports worry.",
                "observed_fact": "The client says they felt worried.",
                "interpretation": "The meeting may be emotionally salient.",
                "confidence": 0.8,
            },
            extraction_method="model_assisted",
            extractor_version="character-dynamics-extraction-v0.2",
            event_status="requires_review",
            idempotency_key="event-key-1",
            created_at=NOW,
        )
        events.add_evidence(
            event_id=event_id,
            message_id="patient-1",
            evidence_type="patient_report",
            start_offset=0,
            end_offset=len(SOURCE_TEXT),
            annotation="The meeting may be emotionally salient.",
        )
    return {
        "manager": manager,
        "service": EventReviewService(manager),
        "run_service": RunService(manager),
        "event_id": "event-1",
    }


def test_list_events_includes_source_excerpt_and_review_status(
    event_review_system,
):
    event = event_review_system["service"].list_events("run-1")[0]

    assert event.event_id == "event-1"
    assert event.event_status == "requires_review"
    assert event.evidence[0].message_id == "patient-1"
    assert event.evidence[0].role == "patient"
    assert event.evidence[0].excerpt == SOURCE_TEXT


def test_event_review_is_immutable_and_idempotent(event_review_system):
    service = event_review_system["service"]
    reviewed_event, review = service.review_event(
        run_id="run-1",
        event_id="event-1",
        decision="accepted",
        reviewer_id="unverified_local_caller",
        rationale="Evidence matches the source text.",
        reviewed_at=NOW,
    )
    repeated_event, repeated_review = service.review_event(
        run_id="run-1",
        event_id="event-1",
        decision="accepted",
        reviewer_id="unverified_local_caller",
        rationale="Evidence matches the source text.",
        reviewed_at="2026-11-17T08:05:00Z",
    )

    assert reviewed_event.event_status == "accepted"
    assert review.review_id == repeated_review.review_id
    assert repeated_event.event_status == "accepted"
    with event_review_system["manager"].connection(
        "operational"
    ) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reviews WHERE event_id = 'event-1'"
        ).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="event_review_immutable"):
            connection.execute(
                "UPDATE event_reviews SET rationale = 'changed' "
                "WHERE event_id = 'event-1'"
            )

    with pytest.raises(EventReviewConflictError):
        service.review_event(
            run_id="run-1",
            event_id="event-1",
            decision="rejected",
            reviewer_id="unverified_local_caller",
            rationale="Conflicting second decision.",
            reviewed_at=NOW,
        )


def test_event_status_cannot_change_without_a_review_record(
    event_review_system,
):
    with event_review_system["manager"].transaction(
        "operational"
    ) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="event_status_requires_review_record",
        ):
            connection.execute(
                "UPDATE events SET event_status = 'accepted' "
                "WHERE event_id = 'event-1'"
            )


def test_event_review_api_returns_evidence_and_authenticated_reviewer(
    event_review_system,
):
    app.dependency_overrides[get_event_review_service] = (
        lambda: event_review_system["service"]
    )
    app.dependency_overrides[get_run_service] = (
        lambda: event_review_system["run_service"]
    )
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/simulation-runs/run-1/events/event-1/review",
            json={
                "decision": "accepted",
                "rationale": "Evidence matches the source text.",
            },
        )
        client.close()
    finally:
        app.dependency_overrides.pop(get_event_review_service, None)
        app.dependency_overrides.pop(get_run_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["event_status"] == "accepted"
    assert body["data"]["evidence"][0]["excerpt"] == SOURCE_TEXT
    assert body["review"]["reviewer_id"] == "local-reviewer"
