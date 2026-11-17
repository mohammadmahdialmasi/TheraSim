"""Command-line interface for paired TheraSim database backups."""

import argparse
from getpass import getpass
import os
from pathlib import Path

from app.persistence.backups import (
    BackupError,
    backup_is_encrypted,
    create_paired_backup,
    restore_paired_backup,
)
from app.persistence.database import DatabaseManager


def _default_backup_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
    return base / "TheraSim" / "backups"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or restore verified paired TheraSim SQLite backups."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup_parser = commands.add_parser("backup", help="create a paired backup")
    backup_parser.add_argument("--data-dir", type=Path)
    backup_parser.add_argument("--backup-root", type=Path)
    backup_parser.add_argument(
        "--encrypt",
        action="store_true",
        help="encrypt the backup; the passphrase cannot be recovered",
    )

    restore_parser = commands.add_parser(
        "restore", help="restore into a new directory without overwriting"
    )
    restore_parser.add_argument("backup_directory", type=Path)
    restore_parser.add_argument("destination_directory", type=Path)

    arguments = parser.parse_args()
    try:
        if arguments.command == "backup":
            manager = DatabaseManager(data_dir=arguments.data_dir)
            passphrase = None
            if arguments.encrypt:
                passphrase = getpass("New backup passphrase: ")
                confirmation = getpass("Confirm backup passphrase: ")
                if passphrase != confirmation:
                    parser.exit(2, "error: backup passphrases do not match.\n")
            backup_directory = create_paired_backup(
                manager,
                arguments.backup_root or _default_backup_root(),
                passphrase=passphrase,
            )
            print(f"Backup created and verified: {backup_directory}")
            return

        passphrase = (
            getpass("Backup passphrase: ")
            if backup_is_encrypted(arguments.backup_directory)
            else None
        )
        restored_directory = restore_paired_backup(
            arguments.backup_directory,
            arguments.destination_directory,
            passphrase=passphrase,
        )
        print(f"Backup restored and verified: {restored_directory}")
    except (BackupError, OSError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
