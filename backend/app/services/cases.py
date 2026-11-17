"""Application service for synthetic case catalog operations."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import sqlite3

from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository


class CaseServiceError(Exception):
    """Base exception for case application operations."""


class CaseNotFoundError(CaseServiceError):
    """The requested case does not exist."""


class CaseVersionNotFoundError(CaseServiceError):
    """The requested case version does not exist."""


class CaseConflictError(CaseServiceError):
    """A case, version, or profile identity conflicts with existing data."""


class CaseDataIntegrityError(CaseServiceError):
    """Persisted case data does not match its expected contract."""


@dataclass(frozen=True, slots=True)
class CaseRecord:
    case_id: str
    case_code: str
    display_name: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CaseVersionRecord:
    case_version_id: str
    case_id: str
    version_number: str
    modality: str
    language: str
    schema_version: str
    content_hash: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class PublicCaseProfileRecord:
    case_version_id: str
    age: int | None
    occupation: str | None
    presenting_concerns: tuple[str, ...]
    initial_disclosure: str | None
    profile_metadata: dict[str, object] | None
    created_at: str


def _parse_json_object(
    value: str | None,
    field_name: str,
) -> dict[str, object] | None:
    if value is None:
        return None

    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CaseDataIntegrityError(
            f"Stored {field_name} contains invalid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise CaseDataIntegrityError(
            f"Stored {field_name} must be a JSON object."
        )

    return parsed


def _parse_string_list(
    value: str,
    field_name: str,
) -> tuple[str, ...]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CaseDataIntegrityError(
            f"Stored {field_name} contains invalid JSON."
        ) from exc

    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise CaseDataIntegrityError(
            f"Stored {field_name} must be a JSON string array."
        )

    return tuple(parsed)


class CaseService:
    """Coordinates operational case catalog use cases.

    This service intentionally has no access to the restricted database.
    It returns application DTOs rather than SQLite rows.
    """

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        self._database_manager = database_manager

    @staticmethod
    def _case_from_row(row: sqlite3.Row) -> CaseRecord:
        return CaseRecord(
            case_id=row["case_id"],
            case_code=row["case_code"],
            display_name=row["display_name"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _version_from_row(row: sqlite3.Row) -> CaseVersionRecord:
        return CaseVersionRecord(
            case_version_id=row["case_version_id"],
            case_id=row["case_id"],
            version_number=row["version_number"],
            modality=row["modality"],
            language=row["language"],
            schema_version=row["schema_version"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _profile_from_row(
        row: sqlite3.Row,
    ) -> PublicCaseProfileRecord:
        return PublicCaseProfileRecord(
            case_version_id=row["case_version_id"],
            age=row["age"],
            occupation=row["occupation"],
            presenting_concerns=_parse_string_list(
                row["presenting_concerns"],
                "presenting_concerns",
            ),
            initial_disclosure=row["initial_disclosure"],
            profile_metadata=_parse_json_object(
                row["profile_metadata"],
                "profile_metadata",
            ),
            created_at=row["created_at"],
        )

    def create_case(
        self,
        *,
        case_id: str,
        case_code: str,
        display_name: str,
        created_at: str,
        updated_at: str,
        status: str = "draft",
    ) -> CaseRecord:
        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                repository = CaseRepository(connection)

                repository.create_case(
                    case_id=case_id,
                    case_code=case_code,
                    display_name=display_name,
                    created_at=created_at,
                    updated_at=updated_at,
                    status=status,
                )

                row = repository.get_case(case_id)

                if row is None:
                    raise CaseServiceError(
                        "Created case could not be retrieved."
                    )

                result = self._case_from_row(row)

        except sqlite3.IntegrityError as exc:
            raise CaseConflictError(
                "The case identifier or case code already exists."
            ) from exc

        return result

    def get_case(self, case_id: str) -> CaseRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = CaseRepository(connection).get_case(case_id)

            return (
                self._case_from_row(row)
                if row is not None
                else None
            )

    def get_case_by_code(
        self,
        case_code: str,
    ) -> CaseRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = CaseRepository(connection).get_case_by_code(
                case_code
            )

            return (
                self._case_from_row(row)
                if row is not None
                else None
            )

    def list_cases(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CaseRecord]:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            rows = CaseRepository(connection).list_cases(
                status=status,
                limit=limit,
                offset=offset,
            )

            return [
                self._case_from_row(row)
                for row in rows
            ]

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
    ) -> CaseVersionRecord:
        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                repository = CaseRepository(connection)

                if repository.get_case(case_id) is None:
                    raise CaseNotFoundError(
                        "Cannot create a version for a missing case."
                    )

                repository.create_case_version(
                    case_version_id=case_version_id,
                    case_id=case_id,
                    version_number=version_number,
                    modality=modality,
                    language=language,
                    schema_version=schema_version,
                    created_at=created_at,
                    content_hash=content_hash,
                )

                row = repository.get_case_version_for_case(
                    case_id,
                    case_version_id,
                )

                if row is None:
                    raise CaseServiceError(
                        "Created case version could not be retrieved."
                    )

                result = self._version_from_row(row)

        except sqlite3.IntegrityError as exc:
            raise CaseConflictError(
                "The case version identifier or version number already exists."
            ) from exc

        return result

    def get_case_version(
        self,
        case_version_id: str,
    ) -> CaseVersionRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = CaseRepository(connection).get_case_version(
                case_version_id
            )

            return (
                self._version_from_row(row)
                if row is not None
                else None
            )

    def get_case_version_for_case(
        self,
        case_id: str,
        case_version_id: str,
    ) -> CaseVersionRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = CaseRepository(
                connection
            ).get_case_version_for_case(
                case_id,
                case_version_id,
            )

            return (
                self._version_from_row(row)
                if row is not None
                else None
            )

    def list_case_versions(
        self,
        case_id: str,
    ) -> list[CaseVersionRecord]:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            rows = CaseRepository(connection).list_case_versions(
                case_id
            )

            return [
                self._version_from_row(row)
                for row in rows
            ]

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
    ) -> PublicCaseProfileRecord:
        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                repository = CaseRepository(connection)

                if repository.get_case_version(
                    case_version_id
                ) is None:
                    raise CaseVersionNotFoundError(
                        "Cannot create a public profile for a missing case version."
                    )

                repository.create_public_profile(
                    case_version_id=case_version_id,
                    created_at=created_at,
                    age=age,
                    occupation=occupation,
                    presenting_concerns=presenting_concerns,
                    initial_disclosure=initial_disclosure,
                    profile_metadata=profile_metadata,
                )

                row = repository.get_public_profile(
                    case_version_id
                )

                if row is None:
                    raise CaseServiceError(
                        "Created public profile could not be retrieved."
                    )

                result = self._profile_from_row(row)

        except sqlite3.IntegrityError as exc:
            raise CaseConflictError(
                "A public profile already exists for this case version."
            ) from exc

        return result

    def get_public_profile(
        self,
        case_version_id: str,
    ) -> PublicCaseProfileRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = CaseRepository(connection).get_public_profile(
                case_version_id
            )

            return (
                self._profile_from_row(row)
                if row is not None
                else None
            )
