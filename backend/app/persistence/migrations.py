"""Checksum-verified, versioned SQLite migrations."""

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import re
import sqlite3

from app.persistence.database import DatabaseManager, DatabaseName


MIGRATIONS_ROOT = Path(__file__).resolve().parent / "migrations"
MIGRATION_PATTERN = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """A migration could not be safely applied."""


def _split_sql(script: str) -> list[str]:
    """Split SQL using SQLite's statement completeness parser."""

    statements: list[str] = []
    buffer: list[str] = []

    for line in script.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer)

        if sqlite3.complete_statement(candidate):
            statement = candidate.strip()

            if statement:
                statements.append(statement)

            buffer = []

    if any(line.strip() for line in buffer):
        raise MigrationError("Migration contains an incomplete SQL statement.")

    return statements


def apply_migrations(
    manager: DatabaseManager,
    database: DatabaseName,
) -> list[str]:
    """Apply pending migrations and verify previously applied checksums."""

    migration_dir = MIGRATIONS_ROOT / database

    if not migration_dir.is_dir():
        raise MigrationError(
            f"Migration directory does not exist for {database}."
        )

    migration_files = sorted(migration_dir.glob("*.sql"))

    if not migration_files:
        raise MigrationError(
            f"No migration files found for {database}."
        )

    parsed: list[tuple[int, Path]] = []

    for path in migration_files:
        match = MIGRATION_PATTERN.match(path.name)

        if not match:
            raise MigrationError(
                f"Invalid migration filename: {path.name}"
            )

        parsed.append((int(match.group(1)), path))

    if len({version for version, _ in parsed}) != len(parsed):
        raise MigrationError("Duplicate migration version detected.")

    with manager.connection(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL UNIQUE,
                description TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

        rows = connection.execute(
            """
            SELECT migration_id, version, checksum
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    applied = {
        int(row["version"]): (
            row["migration_id"],
            row["checksum"],
        )
        for row in rows
    }

    available_versions = {version for version, _ in parsed}
    missing_files = set(applied) - available_versions

    if missing_files:
        raise MigrationError(
            f"Previously applied migration files are missing: {sorted(missing_files)}"
        )

    for version, path in parsed:
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        migration_id = path.stem

        if version in applied:
            previous_id, previous_checksum = applied[version]

            if previous_id != migration_id or previous_checksum != checksum:
                raise MigrationError(
                    f"Applied migration was modified: {migration_id}"
                )

            continue

        expected_version = max(applied, default=0) + 1

        if version != expected_version:
            raise MigrationError(
                f"Expected migration version {expected_version}, got {version}."
            )

        try:
            sql = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MigrationError(
                f"Migration is not valid UTF-8: {migration_id}"
            ) from exc

        description = migration_id.split("_", 1)[1].replace("_", " ")

        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

        try:
            statements = _split_sql(sql)
            requires_foreign_keys_off = (
                "-- therasim: requires_foreign_keys_off" in sql.splitlines()[:3]
            )

            if requires_foreign_keys_off:
                with manager.connection(database) as connection:
                    try:
                        connection.execute("PRAGMA foreign_keys = OFF")
                        if connection.execute(
                            "PRAGMA foreign_keys"
                        ).fetchone()[0] != 0:
                            raise MigrationError(
                                "Foreign keys could not be disabled for migration."
                            )

                        connection.execute("BEGIN IMMEDIATE")

                        for statement in statements:
                            connection.execute(statement)

                        violations = connection.execute(
                            "PRAGMA foreign_key_check"
                        ).fetchall()
                        if violations:
                            raise MigrationError(
                                "Migration would leave foreign key violations."
                            )

                        connection.execute(
                            """
                            INSERT INTO schema_migrations
                            (migration_id, version, description, checksum, applied_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                migration_id,
                                version,
                                description,
                                checksum,
                                timestamp,
                            ),
                        )
                        connection.commit()
                    except BaseException:
                        if connection.in_transaction:
                            connection.rollback()
                        raise
                    finally:
                        connection.execute("PRAGMA foreign_keys = ON")

                    if connection.execute(
                        "PRAGMA foreign_keys"
                    ).fetchone()[0] != 1:
                        raise MigrationError(
                            "Foreign key enforcement could not be restored."
                        )
            else:
                with manager.transaction(database) as connection:
                    for statement in statements:
                        connection.execute(statement)

                    connection.execute(
                        """
                        INSERT INTO schema_migrations
                        (migration_id, version, description, checksum, applied_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            migration_id,
                            version,
                            description,
                            checksum,
                            timestamp,
                        ),
                    )

        except Exception as exc:
            raise MigrationError(
                f"Migration {migration_id} failed: {type(exc).__name__}"
            ) from exc

        applied[version] = (migration_id, checksum)

    return [path.stem for _, path in parsed]
