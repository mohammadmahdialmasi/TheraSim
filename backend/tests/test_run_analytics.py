import pytest
from fastapi.testclient import TestClient

from app.api.routes.analytics import get_run_analytics_service
from app.api.routes.runs import get_run_service
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.evaluations import EvaluationRepository
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.services.evaluations import EvaluationService
from app.services.run_analytics import (
    RunAnalyticsNotFoundError,
    RunAnalyticsService,
)
from app.services.runs import RunService


NOW = "2026-11-18T08:00:00Z"


def create_analytics_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "run-analytics")
    manager.initialize()
    with manager.transaction("operational") as connection:
        cases = CaseRepository(connection)
        cases.create_case(
            case_id="case-analytics",
            case_code="CASE-ANALYTICS",
            display_name="Synthetic client",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        cases.create_case_version(
            case_version_id="version-analytics",
            case_id="case-analytics",
            version_number="1.0",
            modality="ACT",
            language="en",
            schema_version="0.2",
            created_at=NOW,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-analytics",
            case_id="case-analytics",
            case_version_id="version-analytics",
            modality="ACT",
            language="en",
            configuration_version="0.1",
            created_at=NOW,
            status="active",
        )
        SessionRepository(connection).create_session(
            session_id="session-analytics",
            run_id="run-analytics",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )
        EventRepository(connection).create_event(
            event_id="event-analytics",
            run_id="run-analytics",
            session_id="session-analytics",
            sequence_number=1,
            event_type="progress_indicator",
            actor="patient",
            payload={"summary": "Private text is not included in analytics."},
            extraction_method="manual",
            event_status="accepted",
            idempotency_key="event-analytics-key",
            created_at=NOW,
        )
        MemoryRepository(connection).create_memory(
            memory_id="memory-analytics",
            run_id="run-analytics",
            source_session_id="session-analytics",
            memory_type="reported_experience",
            information_class="explicit_disclosure",
            content="Private memory content is not included.",
            memory_version=1,
            created_at=NOW,
            updated_at=NOW,
            status="active",
            confidence=None,
            memory_scope="episodic",
        )
    evaluator = EvaluationService(manager, None)
    return {
        "manager": manager,
        "service": RunAnalyticsService(manager, evaluator),
        "run_service": RunService(manager),
    }


def test_run_analytics_contains_traceable_real_counts_without_case_text(tmp_path):
    system = create_analytics_system(tmp_path)
    snapshot = system["service"].get_snapshot("run-analytics")

    assert snapshot.data_scope == "simulation_run"
    assert snapshot.event_counts == {"accepted": 1}
    assert snapshot.memory_counts == {"active": 1}
    assert snapshot.sessions[0]["session_id"] == "session-analytics"
    assert snapshot.events[0]["event_id"] == "event-analytics"
    assert snapshot.memories[0]["memory_id"] == "memory-analytics"
    serialized = repr(snapshot)
    assert "Private text is not included" not in serialized
    assert "Private memory content is not included" not in serialized
    assert snapshot.limitations


def test_run_analytics_rejects_missing_run(tmp_path):
    system = create_analytics_system(tmp_path)
    with pytest.raises(RunAnalyticsNotFoundError):
        system["service"].get_snapshot("missing-run")


def test_run_analytics_marks_historical_longitudinal_reports_stale(tmp_path):
    system = create_analytics_system(tmp_path)
    with system["manager"].transaction("operational") as connection:
        connection.execute(
            """
            INSERT INTO rubric_versions (
                rubric_version_id, rubric_id, version_number, modality,
                language, schema_version, rubric_definition, created_at
            )
            VALUES (
                'rubric-analytics', 'ACT_LONGITUDINAL_RUBRIC_V0',
                '0.2', 'ACT', 'en', '0.2', '{}', ?
            )
            """,
            (NOW,),
        )
        connection.execute(
            """
            INSERT INTO evaluations (
                evaluation_id, run_id, session_id, evaluation_scope,
                rubric_version_id, transcript_manifest, report_metadata,
                evaluation_revision, status, created_at
            )
            VALUES (
                'evaluation-old', 'run-analytics', NULL, 'longitudinal',
                'rubric-analytics', '[]', '{}', 1, 'requires_review', ?
            )
            """,
            (NOW,),
        )

    snapshot = system["service"].get_snapshot("run-analytics")
    assert len(snapshot.evaluations) == 1
    assert snapshot.evaluations[0]["evaluation_id"] == "evaluation-old"
    assert snapshot.evaluations[0]["stale"] is True


def test_run_analytics_preserves_rubric_scoped_competency_observations(tmp_path):
    system = create_analytics_system(tmp_path)
    with system["manager"].transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="session-analytics-2",
            run_id="run-analytics",
            session_number=2,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )
        messages = MessageRepository(connection)
        messages.create_message(
            message_id="therapist-message-1",
            session_id="session-analytics",
            sequence_number=1,
            role="therapist",
            content="I value connection.",
            created_at=NOW,
        )
        messages.create_message(
            message_id="therapist-message-2",
            session_id="session-analytics-2",
            sequence_number=1,
            role="therapist",
            content="Let us make room for uncertainty.",
            created_at=NOW,
        )
        evaluations = EvaluationRepository(connection)
        for rubric_version_id, version_number, content_hash in (
            ("rubric-session-v02", "0.2", "a" * 64),
            ("rubric-session-v03", "0.3", "b" * 64),
        ):
            evaluations.create_rubric_version(
                rubric_version_id=rubric_version_id,
                rubric_id="ACT_RUBRIC_V0",
                version_number=version_number,
                modality="ACT",
                language="en",
                schema_version="0.2",
                created_at=NOW,
                rubric_definition={},
                content_hash=content_hash,
            )
        for (
            evaluation_id,
            rubric_version_id,
            session_id,
            item_id,
            message_id,
            rating,
            content,
            confidence,
        ) in (
            (
                "eval-session-v02",
                "rubric-session-v02",
                "session-analytics",
                "item-session-v02",
                "therapist-message-1",
                "2",
                "I value connection.",
                "high",
            ),
            (
                "eval-session-v03",
                "rubric-session-v03",
                "session-analytics-2",
                "item-session-v03",
                "therapist-message-2",
                "3",
                "Let us make room for uncertainty.",
                "low",
            ),
        ):
            evaluations.create_evaluation(
                evaluation_id=evaluation_id,
                run_id="run-analytics",
                session_id=session_id,
                evaluation_scope="session",
                rubric_version_id=rubric_version_id,
                evaluation_revision=1,
                status="requires_review",
                created_at=NOW,
                transcript_manifest=[],
                report_metadata={
                    "competencies": {
                        "acceptance": {"confidence": confidence}
                    }
                },
            )
            evaluations.create_item(
                evaluation_item_id=item_id,
                evaluation_id=evaluation_id,
                competency_id="acceptance",
                rating_code=rating,
            )
            start_offset = 0
            evaluations.add_evidence(
                evaluation_item_id=item_id,
                message_id=message_id,
                evidence_role="supporting",
                start_offset=start_offset,
                end_offset=len(content),
                evidence_excerpt=content,
            )
        evaluations.create_evaluation(
            evaluation_id="eval-session-v02-2",
            run_id="run-analytics",
            session_id="session-analytics-2",
            evaluation_scope="session",
            rubric_version_id="rubric-session-v02",
            evaluation_revision=1,
            status="requires_review",
            created_at=NOW,
            transcript_manifest=[],
            report_metadata={
                "competencies": {"acceptance": {"confidence": "low"}}
            },
        )
        evaluations.create_item(
            evaluation_item_id="item-session-v02-2",
            evaluation_id="eval-session-v02-2",
            competency_id="acceptance",
            rating_code="3",
        )
        evaluations.create_item(
            evaluation_item_id="item-session-v02-defusion",
            evaluation_id="eval-session-v02",
            competency_id="defusion",
            rating_code="NE",
        )
        connection.execute(
            """
            UPDATE sessions
            SET status = 'completed', ended_at = ?
            WHERE session_id IN (?, ?)
            """,
            (NOW, "session-analytics", "session-analytics-2"),
        )

    trajectories = system["service"].get_snapshot(
        "run-analytics"
    ).competency_trajectories

    assert len(trajectories) == 3
    by_rubric_and_competency = {
        (item["rubric_version"], item["competency_id"]): item
        for item in trajectories
    }
    acceptance = by_rubric_and_competency[("0.2", "acceptance")]
    assert acceptance["rubric_version_id"] == "rubric-session-v02"
    assert acceptance["rubric_content_hash"] == "a" * 64
    assert acceptance["observations"][0]["rating_code"] == "2"
    assert acceptance["observations"][0]["confidence"] == "high"
    assert acceptance["observations"][0]["evidence_message_ids"] == [
        "therapist-message-1"
    ]
    assert acceptance["observations"][1]["rating_code"] == "3"
    assert acceptance["observations"][1]["confidence"] == "low"
    assert acceptance["missing_completed_sessions"] == []
    assert acceptance["summary"]["evaluable_count"] == 2
    assert acceptance["summary"]["non_evaluable_count"] == 0
    assert acceptance["summary"]["missing_count"] == 0
    assert acceptance["summary"]["evidence_coverage_rate"] == 0.5
    assert acceptance["summary"]["raw_rating_code_change"] == {
        "first_session_id": "session-analytics",
        "first_session_number": 1,
        "first_rating_code": "2",
        "last_session_id": "session-analytics-2",
        "last_session_number": 2,
        "last_rating_code": "3",
        "delta": 1,
    }
    defusion = by_rubric_and_competency[("0.2", "defusion")]
    assert defusion["observations"][0]["rating_code"] == "NE"
    assert defusion["missing_completed_sessions"] == [
        {
            "session_id": "session-analytics-2",
            "session_number": 2,
            "reason": "competency_not_reported",
        }
    ]
    assert defusion["summary"]["non_evaluable_count"] == 1
    assert defusion["summary"]["missing_count"] == 1
    assert defusion["summary"]["raw_rating_code_change"] is None
    acceptance_v03 = [
        item
        for item in trajectories
        if item["rubric_version"] == "0.3"
    ][0]
    assert acceptance_v03["observations"][0]["rating_code"] == "3"
    assert acceptance_v03["observations"][0]["confidence"] == "low"
    assert acceptance_v03["missing_completed_sessions"] == [
        {
            "session_id": "session-analytics",
            "session_number": 1,
            "reason": "no_evaluation_for_rubric",
        }
    ]
    assert "I value connection." not in repr(trajectories)


def test_run_analytics_api_returns_run_scoped_snapshot(tmp_path):
    system = create_analytics_system(tmp_path)
    previous_service = app.dependency_overrides.get(
        get_run_analytics_service
    )
    previous_run_service = app.dependency_overrides.get(get_run_service)
    app.dependency_overrides[get_run_analytics_service] = (
        lambda: system["service"]
    )
    app.dependency_overrides[get_run_service] = lambda: system["run_service"]
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/simulation-runs/run-analytics/analytics"
        )
    finally:
        client.close()
        if previous_service is None:
            app.dependency_overrides.pop(get_run_analytics_service, None)
        else:
            app.dependency_overrides[get_run_analytics_service] = previous_service
        if previous_run_service is None:
            app.dependency_overrides.pop(get_run_service, None)
        else:
            app.dependency_overrides[get_run_service] = previous_run_service

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run-analytics"
    assert data["event_counts"] == {"accepted": 1}
    assert data["events"][0]["event_id"] == "event-analytics"
    assert data["competency_trajectories"] == []
    assert "Private text is not included" not in response.text
