import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.cases import get_case_service
from app.api.routes.runs import (
    get_run_service,
    get_session_service,
)
from app.services.cases import (
    CaseRecord,
    CaseVersionRecord,
    PublicCaseProfileRecord,
)
from app.services.runs import SimulationRunRecord


client = TestClient(app)


class FakeCaseService:
    def __init__(
        self,
        *,
        status="active",
        versions=None,
        profiles=None,
        exists=True,
    ):
        self.case = (
            CaseRecord(
                case_id="case-1",
                case_code="AVA-001",
                display_name="Ava",
                status=status,
                created_at="2026-11-16T10:00:00Z",
                updated_at="2026-11-16T10:00:00Z",
            )
            if exists else None
        )

        self.versions = versions or [
            CaseVersionRecord(
                case_version_id="version-1",
                case_id="case-1",
                version_number="1.0",
                modality="ACT",
                language="fa",
                schema_version="0.2",
                content_hash=None,
                created_at="2026-11-16T10:00:00Z",
            )
        ]

        self.profiles = profiles or {
            "version-1": PublicCaseProfileRecord(
                case_version_id="version-1",
                age=27,
                occupation="Designer",
                presenting_concerns=("anxiety",),
                initial_disclosure="I feel anxious.",
                profile_metadata=None,
                created_at="2026-11-16T10:00:00Z",
            )
        }

    def get_case(self, case_id):
        if self.case is None or self.case.case_id != case_id:
            return None
        return self.case

    def list_case_versions(self, case_id):
        return [
            version for version in self.versions
            if version.case_id == case_id
        ]

    def get_public_profile(self, version_id):
        return self.profiles.get(version_id)


class FakeRunService:
    def __init__(self):
        self.calls = []
        self.run = SimulationRunRecord(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="fa",
            status="initialized",
            configuration_version="0.1.0",
            started_at=None,
            completed_at=None,
            created_at="2026-11-16T12:00:00Z",
        )

    def create_run(self, **kwargs):
        self.calls.append(("create", kwargs))
        self.run = SimulationRunRecord(
            run_id=kwargs["run_id"],
            case_id=kwargs["case_id"],
            case_version_id=kwargs["case_version_id"],
            modality="ACT",
            language="fa",
            status="initialized",
            configuration_version=kwargs["configuration_version"],
            started_at=None,
            completed_at=None,
            created_at=kwargs["created_at"],
            protocol_id=kwargs["protocol_id"],
            protocol_version=kwargs["protocol_version"],
            session_planning_policy=kwargs["session_planning_policy"],
            evaluation_rubric_id=kwargs["evaluation_rubric_id"],
            evaluation_rubric_version=kwargs["evaluation_rubric_version"],
        )
        return self.run

    def get_run(self, run_id):
        if self.run.run_id != run_id:
            return None
        return self.run


    def list_runs(self, *, status=None, limit=20, offset=0):
        self.calls.append(("list", status, limit, offset))

        if status is not None and self.run.status != status:
            return []

        return [self.run][offset:offset + limit]

    def start_run(self, run_id, *, started_at):
        self.calls.append(("start", run_id))
        self.run = SimulationRunRecord(
            run_id=self.run.run_id,
            case_id=self.run.case_id,
            case_version_id=self.run.case_version_id,
            modality=self.run.modality,
            language=self.run.language,
            status="active",
            configuration_version=self.run.configuration_version,
            started_at=started_at,
            completed_at=None,
            created_at=self.run.created_at,
            protocol_id=self.run.protocol_id,
            protocol_version=self.run.protocol_version,
            session_planning_policy=self.run.session_planning_policy,
            evaluation_rubric_id=self.run.evaluation_rubric_id,
            evaluation_rubric_version=self.run.evaluation_rubric_version,
        )
        return self.run


    def _transition_for_test(
        self,
        action,
        run_id,
        *,
        expected_status,
        target_status,
        occurred_at,
    ):
        from app.services.runs import (
            RunNotFoundError,
            RunStateTransitionError,
        )

        if self.run.run_id != run_id:
            raise RunNotFoundError("Run not found.")

        if self.run.status != expected_status:
            raise RunStateTransitionError("Invalid run state transition.")

        self.calls.append((action, run_id))

        started_at = self.run.started_at
        completed_at = self.run.completed_at

        if target_status == "active" and started_at is None:
            started_at = occurred_at

        if target_status == "completed":
            completed_at = occurred_at

        self.run = SimulationRunRecord(
            run_id=self.run.run_id,
            case_id=self.run.case_id,
            case_version_id=self.run.case_version_id,
            modality=self.run.modality,
            language=self.run.language,
            status=target_status,
            configuration_version=self.run.configuration_version,
            started_at=started_at,
            completed_at=completed_at,
            created_at=self.run.created_at,
            protocol_id=self.run.protocol_id,
            protocol_version=self.run.protocol_version,
            session_planning_policy=self.run.session_planning_policy,
            evaluation_rubric_id=self.run.evaluation_rubric_id,
            evaluation_rubric_version=self.run.evaluation_rubric_version,
        )

        return self.run

    def interrupt_run(self, run_id, *, interrupted_at):
        return self._transition_for_test(
            "interrupt",
            run_id,
            expected_status="active",
            target_status="interrupted",
            occurred_at=interrupted_at,
        )

    def resume_run(self, run_id, *, resumed_at):
        return self._transition_for_test(
            "resume",
            run_id,
            expected_status="interrupted",
            target_status="active",
            occurred_at=resumed_at,
        )

    def complete_run(self, run_id, *, completed_at):
        return self._transition_for_test(
            "complete",
            run_id,
            expected_status="active",
            target_status="completed",
            occurred_at=completed_at,
        )


class FakeSessionService:
    def __init__(self):
        self.sessions = []

    def list_sessions(self, run_id):
        return self.sessions


@pytest.fixture
def api_services():
    cases = FakeCaseService()
    runs = FakeRunService()
    sessions = FakeSessionService()

    app.dependency_overrides[get_case_service] = lambda: cases
    app.dependency_overrides[get_run_service] = lambda: runs
    app.dependency_overrides[get_session_service] = lambda: sessions

    yield cases, runs, sessions

    app.dependency_overrides.pop(get_case_service, None)
    app.dependency_overrides.pop(get_run_service, None)
    app.dependency_overrides.pop(get_session_service, None)


def test_create_run_selects_single_matching_public_version(api_services):
    cases, runs, sessions = api_services

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 201

    body = response.json()["data"]
    assert body["case_version_id"] == "version-1"
    assert body["status"] == "initialized"
    assert body["session_count"] == 0
    assert body["protocol_id"] == "ACT_EDUCATIONAL_SIMULATION"
    assert body["protocol_version"] == "0.1"
    assert body["session_planning_policy"] == "flexible"
    assert body["evaluation_rubric_id"] == "ACT_RUBRIC_V0"
    assert body["evaluation_rubric_version"] == "0.2"

    call = runs.calls[0]
    assert call[0] == "create"
    assert call[1]["case_version_id"] == "version-1"
    assert call[1]["configuration_version"] == "0.2.0"
    assert call[1]["session_planning_policy"] == "flexible"


def test_create_run_accepts_explicit_compatible_version(api_services):
    cases, runs, sessions = api_services

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "case_version_id": "version-1",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 201
    assert runs.calls[0][1]["case_version_id"] == "version-1"


def test_create_run_persists_selected_session_planning_policy(api_services):
    cases, runs, sessions = api_services

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "case_version_id": "version-1",
            "modality": "ACT",
            "language": "fa",
            "session_planning_policy": "goal_based",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["session_planning_policy"] == "goal_based"
    assert runs.calls[0][1]["session_planning_policy"] == "goal_based"


def test_create_run_rejects_unknown_session_planning_policy(api_services):
    cases, runs, sessions = api_services

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "case_version_id": "version-1",
            "modality": "ACT",
            "language": "fa",
            "session_planning_policy": "three_sessions",
        },
    )

    assert response.status_code == 422
    assert runs.calls == []


def test_create_run_requires_version_selection_when_ambiguous(api_services):
    cases, runs, sessions = api_services

    second = CaseVersionRecord(
        case_version_id="version-2",
        case_id="case-1",
        version_number="2.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        content_hash=None,
        created_at="2026-11-16T11:00:00Z",
    )

    cases.versions.append(second)
    cases.profiles["version-2"] = PublicCaseProfileRecord(
        case_version_id="version-2",
        age=28,
        occupation="Teacher",
        presenting_concerns=("stress",),
        initial_disclosure="I feel stressed.",
        profile_metadata=None,
        created_at="2026-11-16T11:00:00Z",
    )

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "case_version_selection_required"
    assert runs.calls == []


def test_create_run_rejects_missing_case(api_services):
    cases, runs, sessions = api_services
    cases.case = None

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "missing",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 404
    assert runs.calls == []


def test_create_run_rejects_inactive_case(api_services):
    cases, runs, sessions = api_services
    cases.case = CaseRecord(
        case_id="case-1",
        case_code="AVA-001",
        display_name="Ava",
        status="draft",
        created_at="2026-11-16T10:00:00Z",
        updated_at="2026-11-16T10:00:00Z",
    )

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "case_not_active"
    assert runs.calls == []


def test_create_run_rejects_unavailable_language(api_services):
    cases, runs, sessions = api_services

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "modality": "ACT",
            "language": "en",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "case_version_not_available"
    assert runs.calls == []


def test_create_run_rejects_non_public_version(api_services):
    cases, runs, sessions = api_services
    cases.profiles = {}

    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "case_version_id": "version-1",
            "modality": "ACT",
            "language": "fa",
        },
    )

    assert response.status_code == 422
    assert runs.calls == []


def test_create_run_rejects_unexpected_request_fields(api_services):
    response = client.post(
        "/api/v1/simulation-runs",
        json={
            "case_id": "case-1",
            "modality": "ACT",
            "language": "fa",
            "session_number": 2,
        },
    )

    assert response.status_code == 422


def test_get_run_returns_session_count(api_services):
    cases, runs, sessions = api_services
    sessions.sessions = [object(), object()]

    response = client.get("/api/v1/simulation-runs/run-1")

    assert response.status_code == 200
    assert response.json()["data"]["session_count"] == 2


def test_get_run_returns_404_for_missing_run(api_services):
    response = client.get("/api/v1/simulation-runs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "simulation_run_not_found"


def test_start_run_transitions_initialized_run_to_active(api_services):
    cases, runs, sessions = api_services

    response = client.post("/api/v1/simulation-runs/run-1/start")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"
    assert runs.calls == [("start", "run-1")]


def test_interrupt_run_transitions_active_run_to_interrupted(api_services):
    _, runs, _ = api_services

    runs.start_run(
        "run-1",
        started_at="2026-11-16T12:01:00Z",
    )

    response = client.post(
        "/api/v1/simulation-runs/run-1/interrupt"
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "interrupted"
    assert runs.calls[-1] == ("interrupt", "run-1")


def test_resume_run_transitions_interrupted_run_to_active(api_services):
    _, runs, _ = api_services

    runs.start_run(
        "run-1",
        started_at="2026-11-16T12:01:00Z",
    )
    runs.interrupt_run(
        "run-1",
        interrupted_at="2026-11-16T12:02:00Z",
    )

    response = client.post(
        "/api/v1/simulation-runs/run-1/resume"
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"
    assert runs.calls[-1] == ("resume", "run-1")


def test_complete_run_returns_completed_run(api_services):
    _, runs, sessions = api_services

    runs.start_run(
        "run-1",
        started_at="2026-11-16T12:01:00Z",
    )
    sessions.sessions = [object(), object(), object()]

    response = client.post(
        "/api/v1/simulation-runs/run-1/complete"
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert response.json()["data"]["completed_at"]
    assert response.json()["data"]["session_count"] == 3
    assert runs.calls[-1] == ("complete", "run-1")


def test_interrupt_run_rejects_invalid_state_transition(api_services):
    _, runs, _ = api_services

    response = client.post(
        "/api/v1/simulation-runs/run-1/interrupt"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_run_state_transition"
    assert runs.run.status == "initialized"


def test_resume_run_returns_404_for_missing_run(api_services):
    response = client.post(
        "/api/v1/simulation-runs/missing/resume"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "simulation_run_not_found"


def test_list_runs_returns_persisted_run_metadata(api_services):
    _, runs, sessions = api_services
    sessions.sessions = [object(), object()]

    response = client.get(
        "/api/v1/simulation-runs?limit=10&offset=0"
    )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["run_id"] == "run-1"
    assert response.json()["data"][0]["status"] == "initialized"
    assert response.json()["data"][0]["session_count"] == 2
    assert runs.calls[-1] == ("list", None, 10, 0)


def test_list_runs_can_filter_by_status(api_services):
    _, runs, _ = api_services

    response = client.get(
        "/api/v1/simulation-runs?status=active"
    )

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert runs.calls[-1] == ("list", "active", 20, 0)


def test_list_runs_validates_pagination(api_services):
    response = client.get(
        "/api/v1/simulation-runs?limit=0"
    )

    assert response.status_code == 422
