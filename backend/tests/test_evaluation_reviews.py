import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.api.routes.auth import get_current_user, get_local_auth_service
from app.api.routes.evaluations import get_evaluation_service
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.evaluations import EvaluationRepository
from app.persistence.repositories.operations import ModelRunRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.services.cases import CaseService
from app.services.evaluations import (
    EvaluationReviewUnavailableError,
    EvaluationService,
)
from app.services.local_auth import LocalAuthService
from app.services.runs import RunService


NOW = "2026-11-17T12:00:00Z"


def create_review_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "evaluation-review")
    manager.initialize()
    cases = CaseService(manager)
    cases.create_case(
        case_id="review-case",
        case_code="REVIEW-CASE",
        display_name="Synthetic evaluation case",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    cases.create_case_version(
        case_version_id="review-case-v1",
        case_id="review-case",
        version_number="1.0",
        modality="ACT",
        language="en",
        schema_version="0.2",
        created_at=NOW,
    )
    with manager.transaction("restricted") as connection:
        RestrictedCaseRepository(connection).create_profile(
            restricted_profile_id="review-profile",
            case_id="review-case",
            case_version_id="review-case-v1",
            created_at=NOW,
            clinical_formulation={"type": "synthetic"},
        )
    runs = RunService(manager)
    runs.create_run(
        run_id="review-run",
        case_id="review-case",
        case_version_id="review-case-v1",
        configuration_version="0.1",
        created_at=NOW,
    )
    runs.start_run("review-run", started_at=NOW)
    with manager.transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="review-session",
            run_id="review-run",
            session_number=1,
            status="completed",
            created_at=NOW,
            started_at=NOW,
            ended_at=NOW,
        )
        repository = EvaluationRepository(connection)
        repository.create_rubric_version(
            rubric_version_id="review-rubric",
            rubric_id="ACT_RUBRIC_V0",
            version_number="0.2",
            modality="ACT",
            language="en",
            schema_version="0.2",
            created_at=NOW,
            rubric_definition={},
            content_hash="a" * 64,
        )
        ModelRunRepository(connection).create_model_run(
            model_run_id="review-model-run",
            run_id="review-run",
            session_id="review-session",
            component="evaluator_agent",
            provider="local",
            model_identifier="synthetic-test-model",
            execution_status="completed",
            started_at=NOW,
            generation_parameters={},
        )
        repository.create_evaluation(
            evaluation_id="review-evaluation",
            run_id="review-run",
            session_id="review-session",
            evaluation_scope="session",
            rubric_version_id="review-rubric",
            evaluation_revision=1,
            status="requires_review",
            created_at=NOW,
            transcript_manifest=[],
            evaluator_model_run_id="review-model-run",
            report_metadata={
                "experimental": True,
                "human_review_required": True,
                "evaluator_model": "local-test",
                "competencies": {},
            },
        )

    auth = LocalAuthService(manager)
    session = auth.initialize(
        reviewer_name="Test Reviewer",
        password="a-synthetic-password",
    )
    return {
        "auth": auth,
        "manager": manager,
        "service": EvaluationService(manager),
        "token": session.token,
    }


def test_evaluation_reviews_are_append_only_and_do_not_mutate_report(tmp_path):
    system = create_review_system(tmp_path)
    service = system["service"]

    first = service.add_review(
        evaluation_id="review-evaluation",
        reviewer_user_id="local-reviewer",
        decision="accepted",
        feedback="Evidence and rationale reviewed.",
    )
    second = service.add_review(
        evaluation_id="review-evaluation",
        reviewer_user_id="local-reviewer",
        decision="revision_requested",
        feedback="Revisit the timing rationale.",
    )

    assert first["review_number"] == 1
    assert second["review_number"] == 2
    assert second["reviewer_name"] == "Test Reviewer"
    assert [item["decision"] for item in service.list_reviews(
        evaluation_id="review-evaluation"
    )] == ["accepted", "revision_requested"]
    report = service.get_evaluation(evaluation_id="review-evaluation")
    assert report is not None
    assert report["status"] == "requires_review"
    assert report["evaluation_revision"] == 1

    with pytest.raises(sqlite3.IntegrityError):
        with system["manager"].transaction("operational") as connection:
            connection.execute(
                """
                UPDATE evaluation_reviews
                SET feedback = 'changed'
                WHERE review_id = ?
                """,
                (first["review_id"],),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with system["manager"].transaction("operational") as connection:
            connection.execute(
                "DELETE FROM evaluation_reviews WHERE review_id = ?",
                (first["review_id"],),
            )


def test_historical_evaluation_without_model_provenance_cannot_be_reviewed(
    tmp_path,
):
    system = create_review_system(tmp_path)
    with system["manager"].transaction("operational") as connection:
        EvaluationRepository(connection).create_evaluation(
            evaluation_id="historical-evaluation",
            run_id="review-run",
            session_id="review-session",
            evaluation_scope="session",
            rubric_version_id="review-rubric",
            evaluation_revision=2,
            status="requires_review",
            created_at=NOW,
            transcript_manifest=[],
        )

    with pytest.raises(EvaluationReviewUnavailableError):
        system["service"].add_review(
            evaluation_id="historical-evaluation",
            reviewer_user_id="local-reviewer",
            decision="accepted",
            feedback="No evaluator provenance is available.",
        )


def test_evaluation_review_api_requires_auth_and_records_reviewer(tmp_path):
    system = create_review_system(tmp_path)
    previous_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides.pop(get_current_user, None)
    previous_auth_state = getattr(app.state, "local_auth_service", None)
    app.state.local_auth_service = system["auth"]
    previous_auth = app.dependency_overrides.get(get_local_auth_service)
    previous_evaluation = app.dependency_overrides.get(
        get_evaluation_service
    )
    app.dependency_overrides[get_local_auth_service] = lambda: system["auth"]
    app.dependency_overrides[get_evaluation_service] = (
        lambda: system["service"]
    )
    client = TestClient(app)
    try:
        unauthenticated = client.post(
            "/api/v1/evaluations/review-evaluation/reviews",
            json={
                "decision": "accepted",
                "feedback": "Reviewed.",
            },
        )
        authenticated = client.post(
            "/api/v1/evaluations/review-evaluation/reviews",
            headers={"Authorization": f"Bearer {system['token']}"},
            json={
                "decision": "accepted",
                "feedback": "Reviewed with source messages.",
            },
        )
        report_response = client.get(
            "/api/v1/evaluations/review-evaluation",
            headers={"Authorization": f"Bearer {system['token']}"},
        )
    finally:
        client.close()
        if previous_auth_state is None:
            del app.state.local_auth_service
        else:
            app.state.local_auth_service = previous_auth_state
        if previous_user is not None:
            app.dependency_overrides[get_current_user] = previous_user
        if previous_auth is None:
            app.dependency_overrides.pop(get_local_auth_service, None)
        else:
            app.dependency_overrides[get_local_auth_service] = previous_auth
        if previous_evaluation is None:
            app.dependency_overrides.pop(get_evaluation_service, None)
        else:
            app.dependency_overrides[get_evaluation_service] = previous_evaluation

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 201
    assert authenticated.json()["data"]["reviewer_user_id"] == "local-reviewer"
    assert authenticated.json()["data"]["reviewer_name"] == "Test Reviewer"
    report = report_response.json()["data"]
    assert report["review_status"] == "accepted"
    assert report["human_review_required"] is False
    assert report["reviews"][0]["feedback"] == "Reviewed with source messages."
