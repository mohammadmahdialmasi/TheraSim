import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.character_personality import (
    CharacterPersonalityRepository,
)
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.seed import SeedConflictError, seed_default_case
from app.services.cases import CaseService


def test_database_initialize_seed_command_populates_default_ava_case(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "fresh-install")
    manager.initialize()
    seed_default_case(manager)

    service = CaseService(manager)
    active = service.list_cases(status="active")

    assert len(active) == 1
    assert active[0].case_code == "AVA-001"
    assert service.get_case_by_code("AVA-001").display_name == "Ava (AVA-001)"

    version = service.get_case_version_for_case("case-ava-001", "case-ava-001-v1")
    assert version is not None
    assert version.modality == "ACT"
    assert version.language == "fa"

    public_profile = service.get_public_profile("case-ava-001-v1")
    assert public_profile is not None
    assert public_profile.age == 29
    assert public_profile.occupation == "UX Designer"

    with manager.connection("restricted") as connection:
        restricted = RestrictedCaseRepository(connection)
        profile = restricted.get_profile("case-ava-001", "case-ava-001-v1")
        fact = restricted.get_fact("case-ava-001", "case-ava-001-v1", "AVA-FACT-001")
        personality = CharacterPersonalityRepository(connection).get_active_profile(
            "case-ava-001",
            "case-ava-001-v1",
        )

    assert profile is not None
    assert fact is not None
    assert fact["disclosure_policy"] == "initial_disclosure"
    assert personality is not None
    assert personality["character_id"] == "AVA-001"


def test_seed_default_case_is_idempotent(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "repeat-seed")
    seed_default_case(manager)
    seed_default_case(manager)

    service = CaseService(manager)
    assert len(service.list_cases(status="active")) == 1
    assert service.get_case_by_code("AVA-001") is not None


def test_seed_default_case_rejects_conflicting_case_content(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "conflicting-seed")
    manager.initialize()
    seed_default_case(manager)

    with manager.transaction("operational") as connection:
        connection.execute(
            "UPDATE cases SET display_name = ? WHERE case_code = ?",
            ("Tampered Name", "AVA-001"),
        )

    with pytest.raises(SeedConflictError):
        seed_default_case(manager)
