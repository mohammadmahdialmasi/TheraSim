"""Safe paired backup and restore operations for TheraSim's SQLite databases."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import tempfile
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.persistence.database import (
    DATABASE_FILES,
    DatabaseManager,
    DatabaseName,
)


MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
ENCRYPTED_MANIFEST_VERSION = 2
_ENCRYPTION_CHUNK_SIZE = 1024 * 1024
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DATABASE_NAMES: tuple[DatabaseName, ...] = ("operational", "restricted")


class BackupError(RuntimeError):
    """Raised when a backup or restore cannot be completed safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _derive_backup_key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise ValueError("Backup passphrase must contain at least 12 characters.")
    return Scrypt(
        salt=salt,
        length=32,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    ).derive(passphrase.encode("utf-8"))


def _database_associated_data(name: DatabaseName) -> bytes:
    return f"TheraSim paired backup v{ENCRYPTED_MANIFEST_VERSION}:{name}".encode()


def _encrypt_database(
    source: Path,
    destination: Path,
    *,
    key: bytes,
    nonce: bytes,
    associated_data: bytes,
) -> dict[str, Any]:
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce),
    ).encryptor()
    encryptor.authenticate_additional_data(associated_data)
    plaintext_hash = hashlib.sha256()
    ciphertext_hash = hashlib.sha256()
    plaintext_size = 0
    ciphertext_size = 0

    with source.open("rb") as input_file, destination.open("wb") as output_file:
        for chunk in iter(
            lambda: input_file.read(_ENCRYPTION_CHUNK_SIZE),
            b"",
        ):
            plaintext_hash.update(chunk)
            plaintext_size += len(chunk)
            encrypted = encryptor.update(chunk)
            output_file.write(encrypted)
            ciphertext_hash.update(encrypted)
            ciphertext_size += len(encrypted)
        final_chunk = encryptor.finalize()
        output_file.write(final_chunk)
        ciphertext_hash.update(final_chunk)
        ciphertext_size += len(final_chunk)
        output_file.flush()
        os.fsync(output_file.fileno())

    return {
        "size_bytes": plaintext_size,
        "sha256": plaintext_hash.hexdigest(),
        "encrypted_size_bytes": ciphertext_size,
        "encrypted_sha256": ciphertext_hash.hexdigest(),
        "tag": base64.b64encode(encryptor.tag).decode("ascii"),
    }


def _decode_base64(value: object, *, field_name: str) -> bytes:
    if not isinstance(value, str):
        raise BackupError(f"Encrypted backup metadata field {field_name} is invalid.")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise BackupError(
            f"Encrypted backup metadata field {field_name} is invalid."
        ) from exc


def _decrypt_database(
    source: Path,
    destination: Path,
    *,
    key: bytes,
    nonce: bytes,
    tag: bytes,
    associated_data: bytes,
    expected_size: int,
    expected_hash: str,
) -> None:
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(nonce, tag),
    ).decryptor()
    decryptor.authenticate_additional_data(associated_data)
    plaintext_hash = hashlib.sha256()
    plaintext_size = 0

    try:
        with source.open("rb") as input_file, destination.open("wb") as output_file:
            for chunk in iter(
                lambda: input_file.read(_ENCRYPTION_CHUNK_SIZE),
                b"",
            ):
                plaintext = decryptor.update(chunk)
                output_file.write(plaintext)
                plaintext_hash.update(plaintext)
                plaintext_size += len(plaintext)
            final_chunk = decryptor.finalize()
            output_file.write(final_chunk)
            plaintext_hash.update(final_chunk)
            plaintext_size += len(final_chunk)
            output_file.flush()
            os.fsync(output_file.fileno())
    except InvalidTag as exc:
        destination.unlink(missing_ok=True)
        raise BackupError(
            "Encrypted backup authentication failed; check the passphrase "
            "and backup integrity."
        ) from exc

    if (
        plaintext_size != expected_size
        or plaintext_hash.hexdigest() != expected_hash
    ):
        raise BackupError(
            f"Decrypted database verification failed for {destination.name}."
        )


def _validate_encrypted_backup(
    backup_directory: Path,
    manifest: dict[str, Any],
    passphrase: str | None,
) -> tuple[bytes, dict[str, tuple[Path, dict[str, Any]]]]:
    encryption = manifest.get("encryption")
    if (
        not isinstance(encryption, dict)
        or encryption.get("algorithm") != "AES-256-GCM"
        or encryption.get("kdf") != "scrypt"
        or encryption.get("n") != _SCRYPT_N
        or encryption.get("r") != _SCRYPT_R
        or encryption.get("p") != _SCRYPT_P
    ):
        raise BackupError("Encrypted backup uses unsupported encryption metadata.")
    if passphrase is None:
        raise BackupError("This backup is encrypted and requires a passphrase.")

    salt = _decode_base64(encryption.get("salt"), field_name="salt")
    if len(salt) != 16:
        raise BackupError("Encrypted backup salt has an invalid length.")
    try:
        key = _derive_backup_key(passphrase, salt)
    except ValueError as exc:
        raise BackupError(str(exc)) from exc

    databases = manifest.get("databases")
    if not isinstance(databases, dict) or set(databases) != set(_DATABASE_NAMES):
        raise BackupError("Backup manifest has an unsupported or incomplete format.")

    validated: dict[str, tuple[Path, dict[str, Any]]] = {}
    for name in _DATABASE_NAMES:
        entry = databases[name]
        expected_filename = DATABASE_FILES[name]
        if (
            not isinstance(entry, dict)
            or entry.get("file") != expected_filename
            or entry.get("encrypted_file") != f"{expected_filename}.enc"
            or entry.get("integrity_check") != "ok"
            or not isinstance(entry.get("size_bytes"), int)
            or isinstance(entry.get("size_bytes"), bool)
            or not isinstance(entry.get("sha256"), str)
            or not isinstance(entry.get("encrypted_size_bytes"), int)
            or isinstance(entry.get("encrypted_size_bytes"), bool)
            or not isinstance(entry.get("encrypted_sha256"), str)
        ):
            raise BackupError(f"Backup metadata for {name} is invalid.")

        encrypted_path = backup_directory / entry["encrypted_file"]
        if not encrypted_path.is_file():
            raise BackupError(
                f"Encrypted backup database is missing: {entry['encrypted_file']}"
            )
        if (
            encrypted_path.stat().st_size != entry["encrypted_size_bytes"]
            or _sha256(encrypted_path) != entry["encrypted_sha256"]
        ):
            raise BackupError(
                f"Encrypted backup verification failed for {entry['encrypted_file']}."
            )
        nonce = _decode_base64(entry.get("nonce"), field_name="nonce")
        tag = _decode_base64(entry.get("tag"), field_name="tag")
        if len(nonce) != 12 or len(tag) != 16:
            raise BackupError(f"Encryption metadata for {name} is invalid.")
        validated[name] = (
            encrypted_path,
            {
                **entry,
                "nonce_bytes": nonce,
                "tag_bytes": tag,
            },
        )
    return key, validated


def _integrity_check(path: Path) -> None:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        result = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        raise BackupError(f"Unable to validate SQLite database {path.name}.") from exc
    finally:
        if connection is not None:
            connection.close()

    if result != [("ok",)]:
        raise BackupError(f"SQLite integrity check failed for {path.name}.")


def _sync_file(path: Path) -> None:
    with path.open("r+b") as file_handle:
        os.fsync(file_handle.fileno())


def _secure_directory(path: Path) -> None:
    if os.name != "nt":
        path.chmod(0o700)


def create_paired_backup(
    manager: DatabaseManager,
    backup_root: Path | str,
    *,
    created_at: datetime | None = None,
    passphrase: str | None = None,
) -> Path:
    """Create a verified paired backup, optionally encrypted with a passphrase."""
    salt = secrets.token_bytes(16) if passphrase is not None else None
    key = (
        _derive_backup_key(passphrase, salt)
        if passphrase is not None and salt is not None
        else None
    )

    sources = {
        name: manager.path_for(name)
        for name in _DATABASE_NAMES
    }
    for source in sources.values():
        if not source.is_file():
            raise BackupError(f"Database file does not exist: {source}")

    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Backup timestamp must include a timezone.")
    timestamp_text = timestamp.astimezone(timezone.utc).isoformat()
    backup_root_path = Path(backup_root).expanduser().resolve()
    backup_root_path.mkdir(parents=True, exist_ok=True)
    final_directory = backup_root_path / (
        "therasim-backup-"
        + timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    )
    if final_directory.exists():
        raise BackupError(f"Backup already exists; refusing to overwrite: {final_directory}")

    staging_directory = Path(
        tempfile.mkdtemp(prefix=".therasim-backup-", dir=backup_root_path)
    )
    _secure_directory(staging_directory)
    locked_connections: list[sqlite3.Connection] = []

    try:
        for name in _DATABASE_NAMES:
            connection = sqlite3.connect(
                str(sources[name]),
                timeout=manager.timeout_seconds,
                isolation_level=None,
            )
            connection.execute(
                f"PRAGMA busy_timeout = {int(manager.timeout_seconds * 1000)}"
            )
            locked_connections.append(connection)
            connection.execute("BEGIN EXCLUSIVE")
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            if str(journal_mode).lower() == "wal":
                raise BackupError(
                    f"{sources[name].name} uses WAL mode; stop the application and "
                    "use a WAL-aware backup before continuing."
                )

        entries: dict[str, dict[str, Any]] = {}
        for name in _DATABASE_NAMES:
            source = sources[name]
            filename = DATABASE_FILES[name]
            if key is not None and salt is not None:
                integrity = locked_connections[_DATABASE_NAMES.index(name)].execute(
                    "PRAGMA integrity_check"
                ).fetchall()
                if integrity != [("ok",)]:
                    raise BackupError(
                        f"SQLite integrity check failed for {source.name}."
                    )
                nonce = secrets.token_bytes(12)
                encrypted_filename = f"{filename}.enc"
                encrypted_path = staging_directory / encrypted_filename
                entry = _encrypt_database(
                    source,
                    encrypted_path,
                    key=key,
                    nonce=nonce,
                    associated_data=_database_associated_data(name),
                )
                entry.update(
                    {
                        "file": filename,
                        "encrypted_file": encrypted_filename,
                        "nonce": base64.b64encode(nonce).decode("ascii"),
                        "integrity_check": "ok",
                    }
                )
                entries[name] = entry
            else:
                destination = staging_directory / filename
                shutil.copyfile(source, destination)
                if os.name != "nt":
                    destination.chmod(0o600)
                _sync_file(destination)
                _integrity_check(destination)
                entries[name] = {
                    "file": filename,
                    "size_bytes": destination.stat().st_size,
                    "sha256": _sha256(destination),
                    "integrity_check": "ok",
                }

        manifest = {
            "format_version": (
                ENCRYPTED_MANIFEST_VERSION
                if key is not None and salt is not None
                else MANIFEST_VERSION
            ),
            "created_at": timestamp_text,
            "databases": entries,
        }
        if key is not None and salt is not None:
            manifest["encryption"] = {
                "algorithm": "AES-256-GCM",
                "kdf": "scrypt",
                "salt": base64.b64encode(salt).decode("ascii"),
                "n": _SCRYPT_N,
                "r": _SCRYPT_R,
                "p": _SCRYPT_P,
            }
        manifest_path = staging_directory / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            manifest_path.chmod(0o600)
        _sync_file(manifest_path)

        for connection in reversed(locked_connections):
            if connection.in_transaction:
                connection.rollback()
            connection.close()
        locked_connections.clear()

        if final_directory.exists():
            raise BackupError(
                f"Backup appeared during creation; refusing to overwrite: {final_directory}"
            )
        os.replace(staging_directory, final_directory)
        return final_directory
    except sqlite3.Error as exc:
        raise BackupError(
            "Could not obtain a consistent lock on both databases. "
            "Stop TheraSim and retry."
        ) from exc
    except OSError as exc:
        raise BackupError("Backup file operation failed; no existing backup was replaced.") from exc
    finally:
        for connection in reversed(locked_connections):
            if connection.in_transaction:
                connection.rollback()
            connection.close()
        if staging_directory.exists():
            shutil.rmtree(staging_directory)


def _read_manifest(backup_directory: Path) -> dict[str, Any]:
    manifest_path = backup_directory / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("Backup manifest is missing or invalid.") from exc

    if (
        not isinstance(manifest, dict)
        or manifest.get("format_version")
        not in {MANIFEST_VERSION, ENCRYPTED_MANIFEST_VERSION}
        or not isinstance(manifest.get("databases"), dict)
        or set(manifest["databases"]) != set(_DATABASE_NAMES)
    ):
        raise BackupError("Backup manifest has an unsupported or incomplete format.")
    return manifest


def backup_is_encrypted(backup_directory: Path | str) -> bool:
    """Return whether a validated manifest declares the encrypted format."""

    manifest = _read_manifest(Path(backup_directory).expanduser().resolve())
    return manifest["format_version"] == ENCRYPTED_MANIFEST_VERSION


def _validate_backup(
    backup_directory: Path,
) -> dict[str, tuple[Path, int, str]]:
    manifest = _read_manifest(backup_directory)
    validated: dict[str, tuple[Path, int, str]] = {}

    for name in _DATABASE_NAMES:
        entry = manifest["databases"][name]
        expected_filename = DATABASE_FILES[name]
        if (
            not isinstance(entry, dict)
            or entry.get("file") != expected_filename
            or entry.get("integrity_check") != "ok"
            or not isinstance(entry.get("size_bytes"), int)
            or isinstance(entry.get("size_bytes"), bool)
            or not isinstance(entry.get("sha256"), str)
        ):
            raise BackupError(f"Backup metadata for {name} is invalid.")

        database_path = backup_directory / expected_filename
        if not database_path.is_file():
            raise BackupError(f"Backup database is missing: {expected_filename}")
        if database_path.stat().st_size != entry["size_bytes"]:
            raise BackupError(f"Backup database size does not match: {expected_filename}")
        if _sha256(database_path) != entry["sha256"]:
            raise BackupError(f"Backup checksum does not match: {expected_filename}")
        _integrity_check(database_path)
        validated[name] = (
            database_path,
            entry["size_bytes"],
            entry["sha256"],
        )

    return validated


def restore_paired_backup(
    backup_directory: Path | str,
    destination_directory: Path | str,
    *,
    passphrase: str | None = None,
) -> Path:
    """Restore a verified backup into a new directory without overwriting data."""

    backup_path = Path(backup_directory).expanduser().resolve()
    if not backup_path.is_dir():
        raise BackupError(f"Backup directory does not exist: {backup_path}")
    manifest = _read_manifest(backup_path)
    is_encrypted = manifest["format_version"] == ENCRYPTED_MANIFEST_VERSION
    if is_encrypted:
        key, encrypted_entries = _validate_encrypted_backup(
            backup_path,
            manifest,
            passphrase,
        )
        validated = None
    else:
        validated = _validate_backup(backup_path)
        key = None
        encrypted_entries = None

    destination = Path(destination_directory).expanduser().resolve()
    if destination.exists():
        raise BackupError(
            f"Restore destination already exists; refusing to overwrite: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)

    staging_directory = Path(
        tempfile.mkdtemp(prefix=".therasim-restore-", dir=destination.parent)
    )
    _secure_directory(staging_directory)
    try:
        for name in _DATABASE_NAMES:
            filename = DATABASE_FILES[name]
            target = staging_directory / filename
            if is_encrypted and key is not None and encrypted_entries is not None:
                source, entry = encrypted_entries[name]
                _decrypt_database(
                    source,
                    target,
                    key=key,
                    nonce=entry["nonce_bytes"],
                    tag=entry["tag_bytes"],
                    associated_data=_database_associated_data(name),
                    expected_size=entry["size_bytes"],
                    expected_hash=entry["sha256"],
                )
            else:
                if validated is None:
                    raise BackupError("Validated backup contents are unavailable.")
                source, expected_size, expected_hash = validated[name]
                shutil.copyfile(source, target)
                if (
                    target.stat().st_size != expected_size
                    or _sha256(target) != expected_hash
                ):
                    raise BackupError(
                        f"Backup database changed during restore: {filename}"
                    )
            if os.name != "nt":
                target.chmod(0o600)
            _integrity_check(target)

        if destination.exists():
            raise BackupError(
                f"Restore destination appeared during restore; refusing to overwrite: "
                f"{destination}"
            )
        os.replace(staging_directory, destination)
        return destination
    except OSError as exc:
        raise BackupError(
            "Restore file operation failed; the destination was not published."
        ) from exc
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
