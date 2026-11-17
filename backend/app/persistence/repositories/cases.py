"""Repositories for synthetic case metadata and public profiles."""

import json
import sqlite3
from collections.abc import Mapping, Sequence

from app.persistence.repositories.base import ConnectionBoundRepository


CASE_STATUSES = {"draft", "active", "archived"}


def _json_text(value: object, field_name: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON serializable.") from exc


class CaseRepository(ConnectionBoundRepository):
    """Persistence operations for cases, versions, and public profiles."""

    def create_case(
        self,
        *,
        case_id: str,
        case_code: str,
        display_name: str,
        created_at: str,
        updated_at: str,
        status: str = "draft",
    ) -> None:
        for name, value in (
            ("case_id", case_id),
            ("case_code", case_code),
            ("display_name", display_name),
            ("created_at", created_at),
            ("updated_at", updated_at),
        ):
            self.require_text(value, name)

        if status not in CASE_STATUSES:
            raise ValueError("Invalid case status.")

        self._connection.execute(
            """
            INSERT INTO cases (
                case_id, case_code, display_name, status,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                case_code,
                display_name,
                status,
                created_at,
                updated_at,
            ),
        )

    def get_case(self, case_id: str) -> sqlite3.Row | None:
        self.require_text(case_id, "case_id")
        return self._connection.execute(
            "SELECT * FROM cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

    def get_case_by_code(self, case_code: str) -> sqlite3.Row | None:
        self.require_text(case_code, "case_code")
        return self._connection.execute(
            "SELECT * FROM cases WHERE case_code = ?",
            (case_code,),
        ).fetchone()

    def list_cases(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        self.require_pagination(limit, offset)

        if status is not None and status not in CASE_STATUSES:
            raise ValueError("Invalid case status.")

        if status is None:
            cursor = self._connection.execute(
                """
                SELECT * FROM cases
                ORDER BY created_at DESC, case_id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        else:
            cursor = self._connection.execute(
                """
                SELECT * FROM cases
                WHERE status = ?
                ORDER BY created_at DESC, case_id
                LIMIT ? OFFSET ?
                """,
                (status, limit, offset),
            )

        return list(cursor.fetchall())

    def create_case_version(
        self,
        *,
        case_version_id: str,
        case_id: str,
        version_number: str,
        modality: str,
        language: str,
        schema_version: str,
        created_at: str,
        content_hash: str | None = None,
    ) -> None:
        for name, value in (
            ("case_version_id", case_version_id),
            ("case_id", case_id),
            ("version_number", version_number),
            ("modality", modality),
            ("language", language),
            ("schema_version", schema_version),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        self._connection.execute(
            """
            INSERT INTO case_versions (
                case_version_id, case_id, version_number,
                modality, language, schema_version,
                content_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_version_id,
                case_id,
                version_number,
                modality,
                language,
                schema_version,
                content_hash,
                created_at,
            ),
        )

    def get_case_version(
        self,
        case_version_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(case_version_id, "case_version_id")
        return self._connection.execute(
            "SELECT * FROM case_versions WHERE case_version_id = ?",
            (case_version_id,),
        ).fetchone()

    def get_case_version_for_case(
        self,
        case_id: str,
        case_version_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(case_id, "case_id")
        self.require_text(case_version_id, "case_version_id")

        return self._connection.execute(
            """
            SELECT * FROM case_versions
            WHERE case_id = ? AND case_version_id = ?
            """,
            (case_id, case_version_id),
        ).fetchone()

    def list_case_versions(self, case_id: str) -> list[sqlite3.Row]:
        self.require_text(case_id, "case_id")

        return list(
            self._connection.execute(
                """
                SELECT * FROM case_versions
                WHERE case_id = ?
                ORDER BY created_at, version_number
                """,
                (case_id,),
            ).fetchall()
        )

    def create_public_profile(
        self,
        *,
        case_version_id: str,
        created_at: str,
        age: int | None = None,
        occupation: str | None = None,
        presenting_concerns: Sequence[str] | None = None,
        initial_disclosure: str | None = None,
        profile_metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.require_text(case_version_id, "case_version_id")
        self.require_text(created_at, "created_at")

        if age is not None and (
            isinstance(age, bool) or not isinstance(age, int) or age <= 0
        ):
            raise ValueError("Age must be a positive integer or None.")

        if occupation is not None and not isinstance(occupation, str):
            raise ValueError("Occupation must be a string or None.")

        if presenting_concerns is None:
            presenting_concerns = []

        if isinstance(presenting_concerns, (str, bytes)):
            raise ValueError("Presenting concerns must be a sequence of strings.")

        if not all(isinstance(item, str) for item in presenting_concerns):
            raise ValueError("Every presenting concern must be a string.")

        if profile_metadata is not None and not isinstance(
            profile_metadata, Mapping
        ):
            raise ValueError("Profile metadata must be a mapping or None.")

        concerns_json = _json_text(
            list(presenting_concerns),
            "presenting_concerns",
        )
        metadata_json = (
            _json_text(profile_metadata, "profile_metadata")
            if profile_metadata is not None
            else None
        )

        self._connection.execute(
            """
            INSERT INTO public_case_profiles (
                case_version_id, age, occupation,
                presenting_concerns, initial_disclosure,
                profile_metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_version_id,
                age,
                occupation,
                concerns_json,
                initial_disclosure,
                metadata_json,
                created_at,
            ),
        )

    def get_public_profile(
        self,
        case_version_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(case_version_id, "case_version_id")

        return self._connection.execute(
            """
            SELECT * FROM public_case_profiles
            WHERE case_version_id = ?
            """,
            (case_version_id,),
        ).fetchone()
