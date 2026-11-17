import pytest
from fastapi.testclient import TestClient

from app.api.routes.interaction_requests import (
    get_interaction_request_status_service,
)
from app.main import app
from app.services.interaction_status import (
    InteractionRequestStatusRecord,
)


class FakeInteractionRequestStatusService:
    def __init__(self):
        self.record = InteractionRequestStatusRecord(
            request_id="request-1",
            session_id="session-1",
            processing_status="in_progress",
            therapist_message_id="therapist-1",
            patient_message_id=None,
            error_code=None,
            created_at="2026-11-16T12:00:00Z",
            completed_at=None,
        )
        self.calls = []

    def get_request_status(self, request_id):
        self.calls.append(request_id)

        if self.record is None or self.record.request_id != request_id:
            return None

        return self.record


@pytest.fixture
def status_service():
    service = FakeInteractionRequestStatusService()
    app.dependency_overrides[
        get_interaction_request_status_service
    ] = lambda: service

    yield service

    app.dependency_overrides.pop(
        get_interaction_request_status_service,
        None,
    )


@pytest.fixture
def client(status_service):
    return TestClient(app)


def test_get_interaction_status_returns_operational_metadata(client, status_service):
    response = client.get(
        "/api/v1/interaction-requests/request-1"
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["request_id"] == "request-1"
    assert data["session_id"] == "session-1"
    assert data["processing_status"] == "in_progress"
    assert data["therapist_message_id"] == "therapist-1"
    assert data["patient_message_id"] is None
    assert data["error_code"] is None
    assert data["completed_at"] is None
    assert status_service.calls == ["request-1"]


def test_get_interaction_status_returns_404_for_missing_request(
    client,
    status_service,
):
    response = client.get(
        "/api/v1/interaction-requests/missing"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "interaction_request_not_found"


def test_get_interaction_status_never_exposes_internal_fields(
    client,
    status_service,
):
    response = client.get(
        "/api/v1/interaction-requests/request-1"
    )

    assert response.status_code == 200

    data = response.json()["data"]

    forbidden_fields = {
        "idempotency_key",
        "request_hash",
        "attempt_token",
        "lease_expires_at",
        "last_model_run_id",
    }

    assert forbidden_fields.isdisjoint(data.keys())


def test_get_interaction_status_returns_completed_metadata(
    client,
    status_service,
):
    status_service.record = InteractionRequestStatusRecord(
        request_id="request-1",
        session_id="session-1",
        processing_status="completed",
        therapist_message_id="therapist-1",
        patient_message_id="patient-1",
        error_code=None,
        created_at="2026-11-16T12:00:00Z",
        completed_at="2026-11-16T12:00:12Z",
    )

    response = client.get(
        "/api/v1/interaction-requests/request-1"
    )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["processing_status"] == "completed"
    assert data["patient_message_id"] == "patient-1"
    assert data["completed_at"] == "2026-11-16T12:00:12Z"
