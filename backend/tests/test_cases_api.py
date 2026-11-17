import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.cases import get_case_service
from app.services.cases import (
    CaseRecord,
    CaseVersionRecord,
    PublicCaseProfileRecord,
)


client = TestClient(app)


class FakeCaseService:
    def __init__(self):
        self.cases = [
            CaseRecord(
                case_id="case-1",
                case_code="AVA-001",
                display_name="Ava",
                status="active",
                created_at="2026-11-16T10:00:00Z",
                updated_at="2026-11-16T10:00:00Z",
            ),
            CaseRecord(
                case_id="case-2",
                case_code="AVA-002",
                display_name="Alex",
                status="active",
                created_at="2026-11-16T09:00:00Z",
                updated_at="2026-11-16T09:00:00Z",
            ),
        ]

        self.versions = {
            "case-1": [
                CaseVersionRecord(
                    case_version_id="version-1",
                    case_id="case-1",
                    version_number="1.0",
                    modality="ACT",
                    language="fa",
                    schema_version="0.2",
                    content_hash=None,
                    created_at="2026-11-16T10:00:00Z",
                ),
                CaseVersionRecord(
                    case_version_id="version-2",
                    case_id="case-1",
                    version_number="2.0",
                    modality="ACT",
                    language="en",
                    schema_version="0.2",
                    content_hash=None,
                    created_at="2026-11-16T11:00:00Z",
                ),
            ],
            "case-2": [
                CaseVersionRecord(
                    case_version_id="version-3",
                    case_id="case-2",
                    version_number="1.0",
                    modality="CBT",
                    language="fa",
                    schema_version="0.2",
                    content_hash=None,
                    created_at="2026-11-16T09:00:00Z",
                ),
            ],
        }

        self.profiles = {
            "version-1": PublicCaseProfileRecord(
                case_version_id="version-1",
                age=27,
                occupation="Designer",
                presenting_concerns=("anxiety", "avoidance"),
                initial_disclosure="I have been feeling anxious.",
                profile_metadata={
                    "private_internal_value": "must_not_be_exposed"
                },
                created_at="2026-11-16T10:00:00Z",
            ),
            "version-2": PublicCaseProfileRecord(
                case_version_id="version-2",
                age=27,
                occupation="Designer",
                presenting_concerns=("anxiety",),
                initial_disclosure="I have been feeling anxious.",
                profile_metadata=None,
                created_at="2026-11-16T11:00:00Z",
            ),
            "version-3": PublicCaseProfileRecord(
                case_version_id="version-3",
                age=31,
                occupation="Teacher",
                presenting_concerns=("stress",),
                initial_disclosure="Work has become difficult.",
                profile_metadata=None,
                created_at="2026-11-16T09:00:00Z",
            ),
        }

    def list_cases(self, *, status=None, limit=50, offset=0):
        result = [
            case for case in self.cases
            if status is None or case.status == status
        ]
        return result[offset:offset + limit]

    def get_case(self, case_id):
        return next(
            (case for case in self.cases if case.case_id == case_id),
            None,
        )

    def list_case_versions(self, case_id):
        return self.versions.get(case_id, [])

    def get_public_profile(self, case_version_id):
        return self.profiles.get(case_version_id)


@pytest.fixture
def override_service():
    fake = FakeCaseService()
    app.dependency_overrides[get_case_service] = lambda: fake

    yield fake

    app.dependency_overrides.pop(get_case_service, None)


def test_list_cases_returns_only_active_public_catalog_entries(override_service):
    response = client.get("/api/v1/cases")

    assert response.status_code == 200

    body = response.json()
    assert body["pagination"]["total"] == 2
    assert len(body["data"]) == 2

    ava = next(
        item for item in body["data"]
        if item["case_id"] == "case-1"
    )

    assert ava["modality"] == "ACT"
    assert ava["available_languages"] == ["en", "fa"]


def test_list_cases_filters_by_modality_and_language(override_service):
    response = client.get(
        "/api/v1/cases?modality=ACT&language=fa"
    )

    assert response.status_code == 200

    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["case_id"] == "case-1"


def test_list_cases_supports_pagination(override_service):
    response = client.get(
        "/api/v1/cases?limit=1&offset=1"
    )

    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 2
    assert len(response.json()["data"]) == 1


def test_case_detail_returns_public_presentation_only(override_service):
    response = client.get("/api/v1/cases/case-1")

    assert response.status_code == 200

    body = response.json()
    assert len(body["data"]["versions"]) == 2

    serialized = response.text
    assert "private_internal_value" not in serialized
    assert "profile_metadata" not in serialized


def test_case_detail_returns_404_for_missing_case(override_service):
    response = client.get("/api/v1/cases/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "case_not_found"


@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=101",
        "?offset=-1",
    ],
)
def test_case_list_validates_pagination(override_service, query):
    response = client.get("/api/v1/cases" + query)

    assert response.status_code == 422
