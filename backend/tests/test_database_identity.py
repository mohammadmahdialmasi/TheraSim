import sqlite3

import pytest

from app.persistence.database import DatabaseManager


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "identity-tests")
    result.initialize()
    return result


@pytest.mark.parametrize(
    "database",
    ["operational", "restricted"],
)
def test_connection_reports_its_database_role(manager, database):
    with manager.connection(database) as connection:
        row = connection.execute(
            "SELECT _therasim_database_role()"
        ).fetchone()

        assert row[0] == database


def test_database_role_marker_is_not_available_on_raw_connection():
    connection = sqlite3.connect(":memory:")

    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute(
                "SELECT _therasim_database_role()"
            )
    finally:
        connection.close()
