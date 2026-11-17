"""Explicit SQLite connection and transaction management."""

from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
from typing import Iterator, Literal


DatabaseName = Literal["operational", "restricted"]

DATABASE_FILES = {
    "operational": "therasim.db",
    "restricted": "case_vault.db",
}


class DatabaseManager:
    """Owns the two logically separate SQLite databases."""

    def __init__(
        self,
        data_dir: Path | str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Database timeout must be positive.")

        if data_dir is None:
            configured_dir = os.environ.get("THERASIM_DATA_DIR")

            if configured_dir:
                data_dir = Path(configured_dir).expanduser()
            else:
                project_root = Path(__file__).resolve().parents[3]
                data_dir = project_root / "data"

        self.data_dir = Path(data_dir).expanduser().resolve()
        self.timeout_seconds = timeout_seconds

    def path_for(self, database: DatabaseName) -> Path:
        if database not in DATABASE_FILES:
            raise ValueError("Unknown TheraSim database.")

        return self.data_dir / DATABASE_FILES[database]

    def connect(self, database: DatabaseName) -> sqlite3.Connection:
        """Create a new connection with required SQLite safeguards."""

        path = self.path_for(database)
        path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(
            str(path),
            timeout=self.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                f"PRAGMA busy_timeout = {int(self.timeout_seconds * 1000)}"
            )

            enabled = connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]

            if enabled != 1:
                raise RuntimeError(
                    "SQLite foreign key enforcement could not be enabled."
                )
            connection.create_function(
                "_therasim_database_role",
                0,
                lambda database_name=database: database_name,
                deterministic=True,
            )

        except Exception:
            connection.close()
            raise

        return connection

    @contextmanager
    def connection(
        self,
        database: DatabaseName,
    ) -> Iterator[sqlite3.Connection]:
        """Provide a connection that is always closed after use."""

        connection = self.connect(database)

        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(
        self,
        database: DatabaseName,
        immediate: bool = True,
    ) -> Iterator[sqlite3.Connection]:
        """Execute a short explicit transaction with rollback on failure."""

        with self.connection(database) as connection:
            connection.execute(
                "BEGIN IMMEDIATE" if immediate else "BEGIN"
            )

            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def initialize(self) -> dict[str, list[str]]:
        """Apply migrations independently to both database files."""

        from app.persistence.migrations import apply_migrations

        return {
            "operational": apply_migrations(self, "operational"),
            "restricted": apply_migrations(self, "restricted"),
        }
