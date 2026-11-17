import json
import sqlite3

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "restricted-repository-tests")
    result.initialize()
    return result


def create_profile(
    repository,
    *,
    case_id="case-1",
    version_id="version-1",
    profile_id="profile-1",
):
    repository.create_profile(
        restricted_profile_id=profile_id,
        case_id=case_id,
        case_version_id=version_id,
        clinical_formulation={
            "primary": "performance anxiety",
            "confidence": "hypothesis",
        },
        relevant_personal_history={
            "work_context": "design team",
        },
        maintaining_factors=[
            "overpreparation",
            "avoidance",
        ],
        avoidance_patterns=[
            "withholding ideas in meetings",
        ],
        hypothesized_functions={
            "avoidance": "reducing short-term anxiety",
        },
        initial_safety_baseline={
            "status": "not_assessed",
        },
        patient_simulation_instructions="Simulate a cautious fictional client.",
        created_at=NOW,
    )


def test_create_and_retrieve_restricted_profile_and_fact(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        create_profile(repository)

        repository.create_fact(
            case_id="case-1",
            case_version_id="version-1",
            case_fact_id="FACT-001",
            fact_category="personal_history",
            information_class="established_fact",
            content="The client received a public correction at work.",
            disclosure_policy="contextually_disclosable",
            relevance_metadata={"source": "case_design"},
            created_at=NOW,
        )

        profile = repository.get_profile("case-1", "version-1")
        fact = repository.get_fact(
            "case-1",
            "version-1",
            "FACT-001",
        )

        assert profile is not None
        assert fact is not None

        assert profile["restricted_profile_id"] == "profile-1"
        assert json.loads(profile["clinical_formulation"])["primary"] == (
            "performance anxiety"
        )
        assert json.loads(profile["maintaining_factors"]) == [
            "overpreparation",
            "avoidance",
        ]

        assert fact["information_class"] == "established_fact"
        assert fact["disclosure_policy"] == "contextually_disclosable"
        assert json.loads(fact["relevance_metadata"]) == {
            "source": "case_design",
        }


def test_list_facts_supports_filters_and_pagination(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)
        create_profile(repository)

        facts = [
            (
                "FACT-001",
                "personal_history",
                "established_fact",
                "initial_disclosure",
            ),
            (
                "FACT-002",
                "avoidance",
                "case_hypothesis",
                "contextually_disclosable",
            ),
            (
                "FACT-003",
                "safety",
                "unspecified_information",
                "restricted",
            ),
        ]

        for fact_id, category, information_class, policy in facts:
            repository.create_fact(
                case_id="case-1",
                case_version_id="version-1",
                case_fact_id=fact_id,
                fact_category=category,
                information_class=information_class,
                content=f"Content for {fact_id}",
                disclosure_policy=policy,
                created_at=NOW,
            )

        all_facts = repository.list_facts(
            "case-1",
            "version-1",
        )
        assert len(all_facts) == 3

        hypotheses = repository.list_facts(
            "case-1",
            "version-1",
            information_class="case_hypothesis",
        )
        assert [row["case_fact_id"] for row in hypotheses] == ["FACT-002"]

        restricted = repository.list_facts(
            "case-1",
            "version-1",
            disclosure_policy="restricted",
        )
        assert [row["case_fact_id"] for row in restricted] == ["FACT-003"]

        page = repository.list_facts(
            "case-1",
            "version-1",
            limit=1,
            offset=1,
        )
        assert len(page) == 1
        assert page[0]["case_fact_id"] == "FACT-002"


def test_facts_are_scoped_to_exact_case_version(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        create_profile(
            repository,
            version_id="version-1",
            profile_id="profile-1",
        )
        create_profile(
            repository,
            version_id="version-2",
            profile_id="profile-2",
        )

        for version, content in (
            ("version-1", "Fact from version one"),
            ("version-2", "Fact from version two"),
        ):
            repository.create_fact(
                case_id="case-1",
                case_version_id=version,
                case_fact_id="FACT-SHARED",
                fact_category="test",
                information_class="established_fact",
                content=content,
                disclosure_policy="restricted",
                created_at=NOW,
            )

        first = repository.get_fact(
            "case-1",
            "version-1",
            "FACT-SHARED",
        )
        second = repository.get_fact(
            "case-1",
            "version-2",
            "FACT-SHARED",
        )

        assert first["content"] == "Fact from version one"
        assert second["content"] == "Fact from version two"


def test_repository_rejects_operational_connection(manager):
    with manager.connection("operational") as connection:
        with pytest.raises(ValueError, match="restricted connection"):
            RestrictedCaseRepository(connection)


def test_repository_rejects_unmanaged_sqlite_connection():
    connection = sqlite3.connect(":memory:")

    try:
        with pytest.raises(ValueError, match="restricted connection"):
            RestrictedCaseRepository(connection)
    finally:
        connection.close()


def test_invalid_information_class_is_rejected(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)
        create_profile(repository)

        with pytest.raises(ValueError, match="information_class"):
            repository.create_fact(
                case_id="case-1",
                case_version_id="version-1",
                case_fact_id="FACT-INVALID",
                fact_category="test",
                information_class="confirmed_fact",
                content="Invalid classification.",
                disclosure_policy="restricted",
                created_at=NOW,
            )


def test_invalid_disclosure_policy_is_rejected(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)
        create_profile(repository)

        with pytest.raises(ValueError, match="disclosure_policy"):
            repository.create_fact(
                case_id="case-1",
                case_version_id="version-1",
                case_fact_id="FACT-INVALID",
                fact_category="test",
                information_class="established_fact",
                content="Invalid policy.",
                disclosure_policy="always_disclose",
                created_at=NOW,
            )


def test_fact_requires_existing_restricted_profile(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        with pytest.raises(sqlite3.IntegrityError):
            repository.create_fact(
                case_id="missing-case",
                case_version_id="missing-version",
                case_fact_id="FACT-001",
                fact_category="test",
                information_class="established_fact",
                content="No parent profile exists.",
                disclosure_policy="restricted",
                created_at=NOW,
            )


def test_repository_does_not_commit_or_own_transaction(manager):
    connection = manager.connect("restricted")

    try:
        connection.execute("BEGIN IMMEDIATE")
        repository = RestrictedCaseRepository(connection)

        create_profile(repository)

        assert connection.in_transaction is True

        connection.rollback()
        assert connection.in_transaction is False
    finally:
        connection.close()

    with manager.connection("restricted") as verification:
        row = verification.execute(
            """
            SELECT restricted_profile_id
            FROM restricted_case_profiles
            WHERE case_id = ? AND case_version_id = ?
            """,
            ("case-1", "version-1"),
        ).fetchone()

        assert row is None


def test_profile_rejects_non_json_serializable_data(manager):
    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        with pytest.raises(ValueError, match="JSON serializable"):
            repository.create_profile(
                restricted_profile_id="profile-invalid",
                case_id="case-invalid",
                case_version_id="version-invalid",
                clinical_formulation={"invalid": object()},
                created_at=NOW,
            )
