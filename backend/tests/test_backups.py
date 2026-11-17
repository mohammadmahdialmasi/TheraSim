import json
import sqlite3
from datetime import datetime, timezone

import pytest

from app.persistence.backups import (
    BackupError,
    create_paired_backup,
    restore_paired_backup,
)
from app.persistence.database import DatabaseManager


@pytest.fixture
def initialized_manager(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "source")
    manager.initialize()
    for database in ("operational", "restricted"):
        with manager.transaction(database) as connection:
            connection.execute("CREATE TABLE backup_test (value TEXT NOT NULL)")
            connection.execute(
                "INSERT INTO backup_test (value) VALUES (?)",
                (database,),
            )
    return manager


def test_paired_backup_contains_verified_databases_and_manifest(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "backups",
        created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

    manifest = json.loads((backup_directory / "manifest.json").read_text())
    assert manifest["format_version"] == 1
    assert manifest["created_at"] == "2026-01-02T03:04:05+00:00"
    assert set(manifest["databases"]) == {"operational", "restricted"}
    assert all(
        entry["integrity_check"] == "ok"
        for entry in manifest["databases"].values()
    )

    for database in ("operational", "restricted"):
        filename = initialized_manager.path_for(database).name
        with sqlite3.connect(backup_directory / filename) as connection:
            value = connection.execute(
                "SELECT value FROM backup_test"
            ).fetchone()[0]
        assert value == database


def test_encrypted_paired_backup_round_trips_without_plaintext_files(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "encrypted-backups",
        passphrase="synthetic-backup-passphrase",
    )

    manifest = json.loads((backup_directory / "manifest.json").read_text())
    assert manifest["format_version"] == 2
    assert manifest["encryption"]["algorithm"] == "AES-256-GCM"
    assert sorted(path.name for path in backup_directory.iterdir()) == [
        "case_vault.db.enc",
        "manifest.json",
        "therasim.db.enc",
    ]

    destination = tmp_path / "encrypted-restore"
    restore_paired_backup(
        backup_directory,
        destination,
        passphrase="synthetic-backup-passphrase",
    )
    for database in ("operational", "restricted"):
        filename = initialized_manager.path_for(database).name
        with sqlite3.connect(destination / filename) as connection:
            value = connection.execute(
                "SELECT value FROM backup_test"
            ).fetchone()[0]
        assert value == database


def test_encrypted_restore_rejects_wrong_passphrase_without_publishing(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "encrypted-backups",
        passphrase="synthetic-backup-passphrase",
    )
    destination = tmp_path / "wrong-password-restore"

    with pytest.raises(BackupError, match="requires a passphrase"):
        restore_paired_backup(backup_directory, destination)

    with pytest.raises(BackupError, match="authentication failed"):
        restore_paired_backup(
            backup_directory,
            destination,
            passphrase="different-synthetic-passphrase",
        )

    assert not destination.exists()


def test_encrypted_restore_rejects_ciphertext_tampering(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "encrypted-backups",
        passphrase="synthetic-backup-passphrase",
    )
    encrypted_database = backup_directory / "therasim.db.enc"
    with encrypted_database.open("ab") as output_file:
        output_file.write(b"tampered")

    with pytest.raises(BackupError, match="Encrypted backup verification failed"):
        restore_paired_backup(
            backup_directory,
            tmp_path / "tampered-restore",
            passphrase="synthetic-backup-passphrase",
        )


def test_encrypted_backup_requires_a_long_passphrase(initialized_manager, tmp_path):
    with pytest.raises(ValueError, match="at least 12 characters"):
        create_paired_backup(
            initialized_manager,
            tmp_path / "encrypted-backups",
            passphrase="too-short",
        )


def test_backup_refuses_to_overwrite_a_timestamp_collision(
    initialized_manager,
    tmp_path,
):
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    first = create_paired_backup(
        initialized_manager,
        tmp_path / "backups",
        created_at=timestamp,
    )

    with pytest.raises(BackupError, match="refusing to overwrite"):
        create_paired_backup(
            initialized_manager,
            tmp_path / "backups",
            created_at=timestamp,
        )

    assert (first / "manifest.json").is_file()


def test_restore_validates_and_restores_to_a_new_directory(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "backups",
    )
    destination = tmp_path / "restored-data"

    assert restore_paired_backup(backup_directory, destination) == destination
    for database in ("operational", "restricted"):
        with sqlite3.connect(destination / initialized_manager.path_for(database).name) as connection:
            value = connection.execute(
                "SELECT value FROM backup_test"
            ).fetchone()[0]
        assert value == database


def test_restore_rejects_existing_destination_without_changing_it(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "backups",
    )
    destination = tmp_path / "existing-data"
    destination.mkdir()
    sentinel = destination / "user-file.txt"
    sentinel.write_text("preserve")

    with pytest.raises(BackupError, match="refusing to overwrite"):
        restore_paired_backup(backup_directory, destination)

    assert sentinel.read_text() == "preserve"


def test_restore_rejects_a_modified_backup(
    initialized_manager,
    tmp_path,
):
    backup_directory = create_paired_backup(
        initialized_manager,
        tmp_path / "backups",
    )
    database_path = backup_directory / "therasim.db"
    with database_path.open("ab") as database_file:
        database_file.write(b"tampered")

    with pytest.raises(BackupError, match="size does not match"):
        restore_paired_backup(backup_directory, tmp_path / "restore")


def test_backup_refuses_wal_mode_database(initialized_manager, tmp_path):
    with sqlite3.connect(initialized_manager.path_for("operational")) as connection:
        connection.execute("PRAGMA journal_mode = WAL")

    with pytest.raises(BackupError, match="uses WAL mode"):
        create_paired_backup(initialized_manager, tmp_path / "backups")


def test_backup_fails_clearly_when_a_database_is_locked(
    initialized_manager,
    tmp_path,
):
    manager = DatabaseManager(
        data_dir=initialized_manager.data_dir,
        timeout_seconds=0.1,
    )
    lock = sqlite3.connect(
        initialized_manager.path_for("operational"),
        isolation_level=None,
    )
    lock.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(BackupError, match="Stop TheraSim and retry"):
            create_paired_backup(manager, tmp_path / "backups")
    finally:
        lock.rollback()
        lock.close()
