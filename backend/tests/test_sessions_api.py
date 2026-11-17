import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.sessions import (
    get_run_service,
    get_session_service,
)
from app.services.runs import SimulationRunRecord
from app.services.sessions import (
    SessionConflictError,
    SessionHasUnresolvedInteractionsError,
    SessionInvalidCompletionReasonError,
    SessionMessageRecord,
    SessionNotFoundError,
    SessionOrderViolationError,
    SessionRecord,
    SessionRunNotActiveError,
    SessionRunNotFoundError,
    SessionTransitionError,
)


client = TestClient(app)


NOW = "2026-11-16T12:00:00Z"


class FakeRunService:
    def __init__(self):
        self.exists = True

    def get_run(self, run_id):
        if not self.exists or run_id != "run-1":
            return None

        return SimulationRunRecord(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="fa",
            status="active",
            configuration_version="0.1.0",
            started_at=NOW,
            completed_at=None,
            created_at=NOW,
        )


class FakeSessionService:
    def __init__(self):
        self.sessions = [
            SessionRecord(
                session_id="session-1",
                run_id="run-1",
                session_number=1,
                status="active",
                transcript_version=1,
                started_at=NOW,
                ended_at=None,
                created_at=NOW,
            )
        ]

        self.messages = [
            SessionMessageRecord(
                message_id="message-1",
                sequence_number=1,
                role="therapist",
                content="سلام. امروز چه چیزی برای شما مهم است؟",
                created_at=NOW,
            ),
            SessionMessageRecord(
                message_id="message-2",
                sequence_number=2,
                role="patient",
                content="این روزها اضطراب دارم.",
                created_at=NOW,
            ),
        ]

        self.error = None
        self.calls = []

    def create_next_session(self, **kwargs):
        self.calls.append(("create", kwargs))

        if self.error:
            raise self.error

        result = SessionRecord(
            session_id=kwargs["session_id"],
            run_id=kwargs["run_id"],
            session_number=1,
            status="active",
            transcript_version=1,
            started_at=kwargs.get("started_at") or kwargs["created_at"],
            ended_at=None,
            created_at=kwargs["created_at"],
        )

        self.sessions.append(result)
        return result

    def list_sessions(self, run_id):
        return [
            item for item in self.sessions
            if item.run_id == run_id
        ]

    def get_session(self, session_id):
        return next(
            (
                item for item in self.sessions
                if item.session_id == session_id
            ),
            None,
        )

    def list_messages(self, session_id, *, limit=20, offset=0):
        self.calls.append(
            ("messages", session_id, limit, offset)
        )

        if self.error:
            raise self.error

        if self.get_session(session_id) is None:
            raise SessionNotFoundError()

        return self.messages[offset:offset + limit], len(self.messages)

    def complete_session(
        self,
        session_id,
        *,
        completed_at,
        completion_reason="normal",
    ):
        self.calls.append(
            (
                "complete",
                session_id,
                completed_at,
                completion_reason,
            )
        )

        if self.error:
            raise self.error

        existing = self.get_session(session_id)

        if existing is None:
            raise SessionNotFoundError()

        completed = SessionRecord(
            session_id=existing.session_id,
            run_id=existing.run_id,
            session_number=existing.session_number,
            status="completed",
            transcript_version=existing.transcript_version,
            started_at=existing.started_at,
            ended_at=completed_at,
            created_at=existing.created_at,
        )

        self.sessions = [
            completed if item.session_id == session_id else item
            for item in self.sessions
        ]

        return completed


@pytest.fixture
def api_services():
    run_service = FakeRunService()
    session_service = FakeSessionService()

    app.dependency_overrides[get_run_service] = lambda: run_service
    app.dependency_overrides[get_session_service] = lambda: session_service

    yield run_service, session_service

    app.dependency_overrides.pop(get_run_service, None)
    app.dependency_overrides.pop(get_session_service, None)


def test_create_next_session_returns_201(api_services):
    run_service, session_service = api_services

    response = client.post(
        "/api/v1/simulation-runs/run-1/sessions",
        json={},
    )

    assert response.status_code == 201

    body = response.json()["data"]

    assert body["run_id"] == "run-1"
    assert body["session_number"] == 1
    assert body["status"] == "active"
    assert body["session_id"]

    call = session_service.calls[0]
    assert call[0] == "create"
    assert call[1]["run_id"] == "run-1"


def test_create_session_rejects_arbitrary_session_number(api_services):
    response = client.post(
        "/api/v1/simulation-runs/run-1/sessions",
        json={"session_number": 3},
    )

    assert response.status_code == 422


def test_create_session_maps_order_conflict(api_services):
    _, session_service = api_services

    session_service.error = SessionOrderViolationError()

    response = client.post(
        "/api/v1/simulation-runs/run-1/sessions",
        json={},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "session_order_violation"


def test_list_run_sessions_returns_sequential_sessions(api_services):
    _, session_service = api_services

    response = client.get(
        "/api/v1/simulation-runs/run-1/sessions"
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["session_number"] == 1


def test_list_run_sessions_returns_404_for_missing_run(api_services):
    run_service, _ = api_services
    run_service.exists = False

    response = client.get(
        "/api/v1/simulation-runs/run-1/sessions"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "simulation_run_not_found"


def test_get_session_returns_authorized_metadata(api_services):
    response = client.get("/api/v1/sessions/session-1")

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["session_id"] == "session-1"
    assert body["transcript_version"] == 1
    assert "transcript_hash" not in body


def test_get_session_returns_404_for_missing_session(api_services):
    response = client.get("/api/v1/sessions/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "session_not_found"


def test_list_session_messages_returns_paginated_transcript(api_services):
    _, session_service = api_services

    response = client.get(
        "/api/v1/sessions/session-1/messages?limit=1&offset=1"
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["data"]) == 1
    assert body["data"][0]["sequence_number"] == 2
    assert body["data"][0]["role"] == "patient"

    assert body["pagination"] == {
        "limit": 1,
        "offset": 1,
        "total": 2,
    }

    assert session_service.calls[-1] == (
        "messages",
        "session-1",
        1,
        1,
    )


def test_list_session_messages_validates_pagination(api_services):
    for query in ("?limit=0", "?limit=201", "?offset=-1"):
        response = client.get(
            "/api/v1/sessions/session-1/messages" + query
        )

        assert response.status_code == 422


def test_list_session_messages_maps_missing_session(api_services):
    _, session_service = api_services
    session_service.error = SessionNotFoundError()

    response = client.get(
        "/api/v1/sessions/session-1/messages"
    )

    assert response.status_code == 404


def test_complete_session_returns_completion_contract(api_services):
    _, session_service = api_services

    response = client.post(
        "/api/v1/sessions/session-1/complete",
        json={"completion_reason": "normal"},
    )

    assert response.status_code == 200

    body = response.json()["data"]

    assert body["session_id"] == "session-1"
    assert body["status"] == "completed"
    assert body["transcript_version"] == 1
    assert body["ended_at"]

    assert session_service.calls[-1][3] == "normal"


def test_complete_session_defaults_completion_reason(api_services):
    _, session_service = api_services

    response = client.post(
        "/api/v1/sessions/session-1/complete",
        json={},
    )

    assert response.status_code == 200
    assert session_service.calls[-1][3] == "normal"


def test_complete_session_rejects_unsupported_reason(api_services):
    response = client.post(
        "/api/v1/sessions/session-1/complete",
        json={"completion_reason": "unknown"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (
            SessionNotFoundError(),
            404,
            "session_not_found",
        ),
        (
            SessionRunNotFoundError(),
            404,
            "simulation_run_not_found",
        ),
        (
            SessionRunNotActiveError(),
            409,
            "run_not_active",
        ),
        (
            SessionHasUnresolvedInteractionsError(2),
            409,
            "session_has_unresolved_interactions",
        ),
        (
            SessionTransitionError(),
            409,
            "invalid_session_state_transition",
        ),
        (
            SessionConflictError(),
            409,
            "session_conflict",
        ),
        (
            SessionInvalidCompletionReasonError(),
            422,
            "invalid_completion_reason",
        ),
    ],
)
def test_complete_session_maps_service_errors(
    api_services,
    error,
    status,
    detail,
):
    _, session_service = api_services
    session_service.error = error

    response = client.post(
        "/api/v1/sessions/session-1/complete",
        json={},
    )

    assert response.status_code == status
    assert response.json()["detail"] == detail
