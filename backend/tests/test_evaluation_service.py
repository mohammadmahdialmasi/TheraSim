"""Tests for honest evaluator availability and rubric identifiers."""

import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes.evaluations import (
    _evaluation_response,
    create_run_evaluation,
    create_session_evaluation,
)
from app.persistence.database import DatabaseManager
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.restricted_cases import RestrictedCaseRepository
from app.services.cases import CaseService
from app.services.evaluations import (
    LONGITUDINAL_COMPETENCIES,
    SESSION_COMPETENCIES,
    EvaluationService,
    EvaluationUnavailableError,
)
from app.services.runs import RunService
from app.services.sessions import SessionService

NOW = "2026-11-16T12:00:00Z"


def make_manager(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "evaluation-service-tests")
    manager.initialize()
    return manager


def seed_case(manager):
    CaseService(manager).create_case(
        case_id="case-1",
        case_code="CASE-1",
        display_name="Synthetic Case 1",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    CaseService(manager).create_case_version(
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
            clinical_formulation={"type": "synthetic"},
            created_at=NOW,
        )


def test_session_evaluation_is_unavailable_without_an_evaluator_agent(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run = run_service.create_run(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-1", started_at=NOW)

    session_service = SessionService(manager)
    session_service.create_next_session(
        session_id="session-1",
        run_id="run-1",
        created_at=NOW,
        started_at=NOW,
    )

    with manager.transaction("operational") as connection:
        MessageRepository(connection).create_message(
            message_id="message-session-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content="I feel tense and unsure whether I can trust the process.",
            created_at=NOW,
        )
        SessionRepository(connection).update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

    service = EvaluationService(manager)
    with pytest.raises(EvaluationUnavailableError):
        service.generate_session_evaluation(session_id="session-1")

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0

    with pytest.raises(HTTPException) as error:
        create_session_evaluation("session-1", service=service)
    assert error.value.status_code == 503
    assert error.value.detail == "evaluator_unavailable_experimental"


def test_run_evaluation_is_unavailable_without_an_evaluator_agent(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run_service.create_run(
        run_id="run-2",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-2", started_at=NOW)

    session_service = SessionService(manager)
    for session_id in ("session-2", "session-3"):
        session_service.create_next_session(
            session_id=session_id,
            run_id="run-2",
            created_at=NOW,
            started_at=NOW,
        )
        with manager.transaction("operational") as connection:
            MessageRepository(connection).create_message(
                message_id=f"message-{session_id}",
                session_id=session_id,
                sequence_number=1,
                role="patient",
                content=f"Session content for {session_id} falls within the completed run scope.",
                created_at=NOW,
            )
            SessionRepository(connection).update_status(
                session_id,
                "completed",
                ended_at=NOW,
            )

    service = EvaluationService(manager)
    with pytest.raises(EvaluationUnavailableError):
        service.generate_run_evaluation(run_id="run-2")

    with pytest.raises(HTTPException) as error:
        create_run_evaluation("run-2", service=service)
    assert error.value.status_code == 503
    assert error.value.detail == "evaluator_unavailable_experimental"

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0


def test_run_evaluation_does_not_create_results_for_incomplete_runs(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run_service.create_run(
        run_id="run-3",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-3", started_at=NOW)

    SessionService(manager).create_next_session(
        session_id="session-4",
        run_id="run-3",
        created_at=NOW,
        started_at=NOW,
    )

    service = EvaluationService(manager)

    with pytest.raises(EvaluationUnavailableError):
        service.generate_run_evaluation(run_id="run-3")

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0


def test_competency_ids_match_the_versioned_act_rubrics():
    repository_root = Path(__file__).resolve().parents[2]
    competency_pattern = re.compile(r"\*\*Competency ID:\*\*\s+([a-z0-9_]+)")
    session_rubric = (
        repository_root / "rubrics" / "act" / "ACT_RUBRIC_V0.md"
    ).read_text(encoding="utf-8")
    longitudinal_rubric = (
        repository_root
        / "rubrics"
        / "act"
        / "ACT_LONGITUDINAL_RUBRIC_V0_2.md"
    ).read_text(encoding="utf-8")

    assert tuple(competency_pattern.findall(session_rubric)) == SESSION_COMPETENCIES
    assert (
        tuple(competency_pattern.findall(longitudinal_rubric))
        == LONGITUDINAL_COMPETENCIES
    )


def test_historical_placeholder_evaluations_are_read_as_experimental():
    response = _evaluation_response(
        {
            "evaluation_id": "legacy-evaluation",
            "run_id": "legacy-run",
            "session_id": "legacy-session",
            "evaluation_scope": "session",
            "rubric_id": "ACT_RUBRIC_V0",
            "rubric_version": "0.2",
            "status": "completed",
            "created_at": NOW,
            "overall_summary": "Placeholder summary",
            "evaluator_model_run_id": None,
        },
        service=None,
    )

    assert response.status == "experimental"
    assert response.items == []
    assert "withheld" in response.overall_summary
