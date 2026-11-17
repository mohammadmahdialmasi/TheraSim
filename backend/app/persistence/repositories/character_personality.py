"""Restricted repository for versioned character personality profiles."""

import hashlib
import json
import sqlite3

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import require_text


PROFILE_STATUSES = {"draft", "reviewed", "active", "retired"}
ALLOWED_STATUS_TRANSITIONS = {
    "draft": {"reviewed"},
    "reviewed": {"draft", "active"},
    "active": {"retired"},
    "retired": set(),
}


class CharacterPersonalityRepository(ConnectionBoundRepository):
    """Stores immutable profile content in the restricted case vault."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)
        try:
            row = self._connection.execute(
                "SELECT _therasim_database_role()"
            ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError(
                "CharacterPersonalityRepository requires a restricted connection."
            ) from exc
        if row is None or row[0] != "restricted":
            raise ValueError("A restricted database connection is required.")

    @staticmethod
    def _validate_profile_document(
        *, profile_json: str, content_hash: str,
        personality_profile_id: str, character_id: str,
        case_id: str, case_version_id: str, profile_version: int,
    ) -> None:
        require_text(profile_json, "profile_json")
        require_text(content_hash, "content_hash")
        try:
            document = json.loads(profile_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Profile content must be valid JSON.") from exc
        if not isinstance(document, dict):
            raise ValueError("Profile content must be a JSON object.")
        expected = {
            "personality_profile_id": personality_profile_id,
            "character_id": character_id,
            "case_id": case_id,
            "case_version_id": case_version_id,
            "profile_version": profile_version,
        }
        for key, value in expected.items():
            if document.get(key) != value:
                raise ValueError(f"Profile JSON identity does not match {key}.")
        canonical = json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        if canonical != profile_json:
            raise ValueError("Profile JSON must use canonical serialization.")
        actual_hash = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
        if actual_hash != content_hash:
            raise ValueError("Profile content hash does not match its content.")

    def next_profile_version(self, case_id: str, case_version_id: str) -> int:
        require_text(case_id, "case_id")
        require_text(case_version_id, "case_version_id")
        row = self._connection.execute(
            """SELECT COALESCE(MAX(profile_version), 0) AS latest_version
               FROM character_personality_profiles
               WHERE case_id = ? AND case_version_id = ?""",
            (case_id, case_version_id),
        ).fetchone()
        return int(row["latest_version"]) + 1

    def create_profile(
        self, *, personality_profile_id: str, character_id: str,
        case_id: str, case_version_id: str, profile_version: int,
        personality_schema_version: str, theory_bundle_version: str,
        profile_json: str, content_hash: str, created_at: str,
    ) -> None:
        for name, value in (
            ("personality_profile_id", personality_profile_id),
            ("character_id", character_id), ("case_id", case_id),
            ("case_version_id", case_version_id),
            ("personality_schema_version", personality_schema_version),
            ("theory_bundle_version", theory_bundle_version),
            ("created_at", created_at),
        ):
            require_text(value, name)
        if isinstance(profile_version, bool) or not isinstance(profile_version, int) or profile_version < 1:
            raise ValueError("Profile version must be a positive integer.")
        self._validate_profile_document(
            profile_json=profile_json, content_hash=content_hash,
            personality_profile_id=personality_profile_id,
            character_id=character_id, case_id=case_id,
            case_version_id=case_version_id, profile_version=profile_version,
        )
        self._connection.execute(
            """INSERT INTO character_personality_profiles (
                   personality_profile_id, character_id, case_id, case_version_id,
                   profile_version, personality_schema_version, theory_bundle_version,
                   authoring_status, profile_json, content_hash, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
            (personality_profile_id, character_id, case_id, case_version_id,
             profile_version, personality_schema_version, theory_bundle_version,
             profile_json, content_hash, created_at),
        )

    def get_profile(self, personality_profile_id: str) -> sqlite3.Row | None:
        require_text(personality_profile_id, "personality_profile_id")
        return self._connection.execute(
            "SELECT * FROM character_personality_profiles WHERE personality_profile_id = ?",
            (personality_profile_id,),
        ).fetchone()

    def get_active_profile(self, case_id: str, case_version_id: str) -> sqlite3.Row | None:
        require_text(case_id, "case_id")
        require_text(case_version_id, "case_version_id")
        return self._connection.execute(
            """SELECT * FROM character_personality_profiles
               WHERE case_id = ? AND case_version_id = ? AND authoring_status = 'active'""",
            (case_id, case_version_id),
        ).fetchone()

    def list_profiles(self, case_id: str, case_version_id: str) -> list[sqlite3.Row]:
        require_text(case_id, "case_id")
        require_text(case_version_id, "case_version_id")
        return list(self._connection.execute(
            """SELECT * FROM character_personality_profiles
               WHERE case_id = ? AND case_version_id = ?
               ORDER BY profile_version""",
            (case_id, case_version_id),
        ).fetchall())

    def set_authoring_status(self, personality_profile_id: str, new_status: str) -> bool:
        require_text(personality_profile_id, "personality_profile_id")
        if new_status not in PROFILE_STATUSES:
            raise ValueError("Invalid personality profile status.")
        row = self.get_profile(personality_profile_id)
        if row is None:
            raise ValueError("Personality profile does not exist.")
        current = row["authoring_status"]
        if current == new_status:
            return False
        if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise ValueError(f"Invalid profile status transition: {current} -> {new_status}.")
        if new_status == "active":
            self._connection.execute(
                """UPDATE character_personality_profiles
                   SET authoring_status = 'retired'
                   WHERE case_id = ? AND case_version_id = ?
                     AND authoring_status = 'active'""",
                (row["case_id"], row["case_version_id"]),
            )
        self._connection.execute(
            "UPDATE character_personality_profiles SET authoring_status = ? WHERE personality_profile_id = ?",
            (new_status, personality_profile_id),
        )
        return True
