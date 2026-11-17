"""Application service for authoring versioned character profiles."""

import hashlib
import json

from app.persistence.database import DatabaseManager
from app.persistence.repositories.character_personality import CharacterPersonalityRepository
from app.services.character_model import CharacterPersonalityProfile


class CharacterPersonalityService:
    """Validates and versions authored personality profiles in the case vault."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        self._database_manager = database_manager

    def create_profile(
        self, profile: CharacterPersonalityProfile, *, created_at: str
    ) -> dict[str, object]:
        if not isinstance(profile, CharacterPersonalityProfile):
            raise TypeError("A CharacterPersonalityProfile is required.")
        if profile.authoring_status != "draft":
            raise ValueError("New personality profiles must start as drafts.")
        if not isinstance(created_at, str) or not created_at.strip():
            raise ValueError("created_at must be a non-empty string.")
        with self._database_manager.transaction("restricted") as connection:
            repository = CharacterPersonalityRepository(connection)
            version = repository.next_profile_version(profile.case_id, profile.case_version_id)
            versioned_profile = profile.model_copy(update={"profile_version": version})
            document = versioned_profile.model_dump(mode="json", exclude={"authoring_status"})
            profile_json = json.dumps(
                document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            content_hash = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
            repository.create_profile(
                personality_profile_id=versioned_profile.personality_profile_id,
                character_id=versioned_profile.character_id,
                case_id=versioned_profile.case_id,
                case_version_id=versioned_profile.case_version_id,
                profile_version=version,
                personality_schema_version=versioned_profile.personality_schema_version,
                theory_bundle_version=versioned_profile.theory_bundle_version,
                profile_json=profile_json,
                content_hash=content_hash,
                created_at=created_at,
            )
            row = repository.get_profile(versioned_profile.personality_profile_id)
            if row is None:
                raise RuntimeError("Created personality profile could not be read.")
            return dict(row)

    def set_profile_status(self, personality_profile_id: str, new_status: str) -> bool:
        with self._database_manager.transaction("restricted") as connection:
            return CharacterPersonalityRepository(connection).set_authoring_status(
                personality_profile_id, new_status
            )

    def review_profile(self, personality_profile_id: str) -> bool:
        return self.set_profile_status(personality_profile_id, "reviewed")

    def activate_profile(self, personality_profile_id: str) -> bool:
        return self.set_profile_status(personality_profile_id, "active")

    def retire_profile(self, personality_profile_id: str) -> bool:
        return self.set_profile_status(personality_profile_id, "retired")

    def get_active_profile(self, case_id: str, case_version_id: str) -> dict[str, object] | None:
        with self._database_manager.connection("restricted") as connection:
            row = CharacterPersonalityRepository(connection).get_active_profile(
                case_id, case_version_id
            )
            return dict(row) if row is not None else None
