import sqlite3

import pytest

from app.persistence.database import DatabaseManager


@pytest.fixture
def manager(tmp_path):
    return DatabaseManager(data_dir=tmp_path / "therasim-data")


def test_database_files_are_separate(manager):
    manager.initialize()

    operational = manager.path_for("operational")
    restricted = manager.path_for("restricted")

    assert operational.is_file()
    assert restricted.is_file()
    assert operational != restricted


def test_migrations_create_separate_schemas(manager):
    manager.initialize()

    with manager.connection("operational") as connection:
        operational_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    with manager.connection("restricted") as connection:
        restricted_tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "cases",
        "case_versions",
        "simulation_runs",
        "sessions",
        "messages",
        "interaction_requests",
        "model_runs",
        "audit_events",
        "schema_migrations",
    }.issubset(operational_tables)

    assert {
        "restricted_case_profiles",
        "case_facts",
        "schema_migrations",
    }.issubset(restricted_tables)

    assert "restricted_case_profiles" not in operational_tables
    assert "messages" not in restricted_tables


def test_migrations_are_idempotent(manager):
    first = manager.initialize()
    second = manager.initialize()

    assert first == second

    with manager.connection("operational") as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ).fetchone()[0]

    assert count == 10


def test_foreign_keys_are_enabled_on_every_connection(manager):
    manager.initialize()

    with manager.connection("operational") as connection:
        result = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert result == 1


def test_transaction_rolls_back_on_error(manager):
    manager.initialize()

    with pytest.raises(RuntimeError):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                INSERT INTO cases
                (case_id, case_code, display_name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("case-1", "TEST-001", "Test", "draft", "now", "now"),
            )
            raise RuntimeError("simulate failure")

    with manager.connection("operational") as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0]

    assert count == 0


def test_foreign_key_rejects_orphan_case_version(manager):
    manager.initialize()

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                INSERT INTO case_versions
                (case_version_id, case_id, version_number, modality,
                 language, schema_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("version-1", "missing-case", "0.1", "ACT", "fa", "0.1", "now"),
            )


def test_unknown_database_name_is_rejected(manager):
    with pytest.raises(ValueError):
        manager.path_for("unknown")
