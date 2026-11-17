import pytest

from app.persistence.database import DatabaseManager
from app.services.cases import (
    CaseConflictError,
    CaseDataIntegrityError,
    CaseNotFoundError,
    CaseRecord,
    CaseService,
    CaseVersionNotFoundError,
    CaseVersionRecord,
    PublicCaseProfileRecord,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "case-service-tests")
    result.initialize()
    return result


@pytest.fixture
def service(manager):
    return CaseService(manager)


def create_case(service, *, case_id="case-1", status="active"):
    return service.create_case(
        case_id=case_id,
        case_code=f"CODE-{case_id}",
        display_name=f"Case {case_id}",
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def create_version(
    service,
    *,
    case_id="case-1",
    version_id="version-1",
    version_number="1.0",
):
    return service.create_case_version(
        case_version_id=version_id,
        case_id=case_id,
        version_number=version_number,
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )


def test_create_case_returns_typed_dto(service):
    result = create_case(service)

    assert isinstance(result, CaseRecord)
    assert result.case_id == "case-1"
    assert result.case_code == "CODE-case-1"
    assert result.status == "active"

    retrieved = service.get_case("case-1")

    assert retrieved == result
    assert service.get_case("missing-case") is None


def test_get_case_by_code_and_list_filters(service):
    create_case(service, case_id="case-1", status="active")
    create_case(service, case_id="case-2", status="draft")
    create_case(service, case_id="case-3", status="active")

    assert service.get_case_by_code("CODE-case-2").case_id == "case-2"
    assert service.get_case_by_code("missing-code") is None

    active = service.list_cases(status="active")

    assert len(active) == 2
    assert all(item.status == "active" for item in active)

    page = service.list_cases(limit=1, offset=1)

    assert len(page) == 1


def test_duplicate_case_is_reported_as_domain_conflict(service):
    create_case(service)

    with pytest.raises(CaseConflictError):
        service.create_case(
            case_id="case-2",
            case_code="CODE-case-1",
            display_name="Duplicate code",
            created_at=NOW,
            updated_at=NOW,
        )

    assert service.get_case("case-2") is None


def test_create_and_list_case_versions(service):
    create_case(service)

    result = create_version(service)

    assert isinstance(result, CaseVersionRecord)
    assert result.case_version_id == "version-1"
    assert result.case_id == "case-1"
    assert result.modality == "ACT"

    assert service.get_case_version("version-1") == result
    assert service.get_case_version_for_case(
        "case-1",
        "version-1",
    ) == result

    assert service.get_case_version_for_case(
        "other-case",
        "version-1",
    ) is None

    versions = service.list_case_versions("case-1")

    assert versions == [result]


def test_create_case_version_requires_existing_case(service):
    with pytest.raises(CaseNotFoundError):
        create_version(service, case_id="missing-case")

    assert service.get_case_version("version-1") is None


def test_duplicate_case_version_is_reported_as_conflict(service):
    create_case(service)
    create_version(service)

    with pytest.raises(CaseConflictError):
        create_version(
            service,
            version_id="version-2",
            version_number="1.0",
        )

    assert service.get_case_version("version-2") is None


def test_public_profile_is_returned_as_decoded_dto(service):
    create_case(service)
    create_version(service)

    result = service.create_public_profile(
        case_version_id="version-1",
        age=29,
        occupation="UX designer",
        presenting_concerns=[
            "meeting anxiety",
            "overpreparation",
        ],
        initial_disclosure="Cautious initial presentation.",
        profile_metadata={
            "language": "fa",
            "synthetic": True,
        },
        created_at=NOW,
    )

    assert isinstance(result, PublicCaseProfileRecord)
    assert result.age == 29
    assert result.occupation == "UX designer"
    assert result.presenting_concerns == (
        "meeting anxiety",
        "overpreparation",
    )
    assert result.profile_metadata == {
        "language": "fa",
        "synthetic": True,
    }

    assert service.get_public_profile("version-1") == result


def test_public_profile_requires_existing_case_version(service):
    with pytest.raises(CaseVersionNotFoundError):
        service.create_public_profile(
            case_version_id="missing-version",
            created_at=NOW,
        )

    assert service.get_public_profile("missing-version") is None


def test_duplicate_public_profile_is_reported_as_conflict(service):
    create_case(service)
    create_version(service)

    service.create_public_profile(
        case_version_id="version-1",
        created_at=NOW,
    )

    with pytest.raises(CaseConflictError):
        service.create_public_profile(
            case_version_id="version-1",
            created_at=NOW,
        )


def test_invalid_persisted_profile_json_is_rejected(service, manager):
    create_case(service)
    create_version(service)

    service.create_public_profile(
        case_version_id="version-1",
        presenting_concerns=["anxiety"],
        created_at=NOW,
    )

    with manager.transaction("operational") as connection:
        connection.execute(
            """
            UPDATE public_case_profiles
            SET presenting_concerns = ?
            WHERE case_version_id = ?
            """,
            ("{}", "version-1"),
        )

    with pytest.raises(
        CaseDataIntegrityError,
        match="JSON string array",
    ):
        service.get_public_profile("version-1")


def test_service_requires_database_manager():
    with pytest.raises(TypeError, match="DatabaseManager"):
        CaseService(object())
