import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.interactions import get_interaction_service
from app.services.interactions import (
    InteractionAttemptOwnershipLostError,
    InteractionGenerationError,
    InteractionIdempotencyConflictError,
    InteractionRecord,
    InteractionSessionBusyError,
    InteractionSessionNotFoundError,
    InteractionSessionNotActiveError,
    InteractionRunNotActiveError,
)


client = TestClient(app)


class FakeInteractionService:
    def __init__(self, result=None, error=None):
        self.result = result or InteractionRecord(
            status="completed",
            session_id="session-1",
            request_id="request-1",
            attempt_number=1,
            therapist_message_id="therapist-1",
            therapist_content="در جلسه مضطرب شدم.",
            patient_message_id="patient-1",
            patient_content="می‌توانید بیشتر توضیح دهید؟",
        )
        self.error = error
        self.calls = []

    def handle_message(self, *, session_id, idempotency_key, content):
        self.calls.append((session_id, idempotency_key, content))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def override_service():
    fake = FakeInteractionService()
    app.dependency_overrides[get_interaction_service] = lambda: fake

    yield fake

    app.dependency_overrides.pop(get_interaction_service, None)


def test_create_message_returns_completed_interaction(override_service):
    response = client.post(
        "/api/v1/sessions/session-1/messages",
        headers={"Idempotency-Key": "api-key-1"},
        json={"content": "در جلسه مضطرب شدم."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["patient_content"] == "می‌توانید بیشتر توضیح دهید؟"
    assert override_service.calls == [
        ("session-1", "api-key-1", "در جلسه مضطرب شدم.")
    ]


def test_create_message_returns_202_when_processing(override_service):
    override_service.result = InteractionRecord(
        status="processing",
        session_id="session-1",
        request_id="request-2",
        attempt_number=1,
        therapist_message_id="therapist-2",
        therapist_content="در جلسه مضطرب شدم.",
    )

    response = client.post(
        "/api/v1/sessions/session-1/messages",
        headers={"Idempotency-Key": "api-key-2"},
        json={"content": "در جلسه مضطرب شدم."},
    )

    assert response.status_code == 202
    assert response.headers["retry-after"] == "2"
    assert response.json()["patient_message_id"] is None


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (InteractionSessionNotFoundError(), 404, "session_not_found"),
        (InteractionSessionNotActiveError(), 409, "session_not_active"),
        (InteractionRunNotActiveError(), 409, "run_not_active"),
        (InteractionIdempotencyConflictError(), 409, "idempotency_conflict"),
        (InteractionSessionBusyError(), 409, "session_has_unresolved_interaction"),
        (InteractionAttemptOwnershipLostError(), 409, "interaction_attempt_ownership_lost"),
        (InteractionGenerationError("provider_unavailable"), 503, "provider_unavailable"),
        (InteractionGenerationError("invalid_agent_output"), 502, "invalid_agent_output"),
    ],
)
def test_create_message_maps_service_errors(
    override_service,
    error,
    expected_status,
    expected_detail,
):
    override_service.error = error

    response = client.post(
        "/api/v1/sessions/session-1/messages",
        headers={"Idempotency-Key": "api-error-key"},
        json={"content": "سلام."},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_create_message_requires_idempotency_header(override_service):
    response = client.post(
        "/api/v1/sessions/session-1/messages",
        json={"content": "سلام."},
    )

    assert response.status_code == 422
    assert override_service.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"content": ""},
        {"content": "   "},
        {"content": "سلام.", "unexpected": True},
    ],
)
def test_create_message_validates_request_body(override_service, payload):
    response = client.post(
        "/api/v1/sessions/session-1/messages",
        headers={"Idempotency-Key": "validation-key"},
        json=payload,
    )

    assert response.status_code == 422
    assert override_service.calls == []


def test_create_message_returns_503_when_service_is_unconfigured():
    app.dependency_overrides.pop(get_interaction_service, None)

    response = client.post(
        "/api/v1/sessions/session-1/messages",
        headers={"Idempotency-Key": "not-configured-key"},
        json={"content": "سلام."},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "interaction_service_unavailable"
