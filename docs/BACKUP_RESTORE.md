# TheraSim database backup and restore

The operational and restricted SQLite databases must be backed up and restored
as a pair. The backup command uses exclusive SQLite locks while copying both
files, refuses WAL-mode databases, validates each copy with
`PRAGMA integrity_check`, writes a SHA-256 manifest, and publishes the completed
directory only after verification. If a database is busy, stop TheraSim and
retry. A failed operation does not replace an existing backup.

The pair contains two independently managed SQLite databases; SQLite does not
provide a single cross-file transaction for their application-level updates.
The backup ensures each database is a consistent SQLite snapshot and captures
both under held locks, but it is not a distributed transaction across the two
files. Stop TheraSim before backup when an application-level point-in-time pair
is required.

## Create a backup

From the `backend` directory, using the project's Python environment:

```powershell
..\.venv\Scripts\python.exe -m app.persistence.backup_cli backup
```

Plain backups remain supported for compatibility. To encrypt both database
files, explicitly request encryption:

```powershell
..\.venv\Scripts\python.exe -m app.persistence.backup_cli backup --encrypt
```

The CLI prompts twice for a passphrase of at least 12 characters. The backup
uses AES-256-GCM with a fresh nonce per database and derives its key with
scrypt. Plain database files are not copied into the encrypted backup
directory. The passphrase is never stored and cannot be recovered; retain it
separately from the backup. If it is lost, the encrypted backup cannot be
restored. The manifest contains non-secret format and integrity metadata.

By default, backups are placed under `%LOCALAPPDATA%\TheraSim\backups` on
Windows. Specify a data directory or backup root when needed:

```powershell
..\.venv\Scripts\python.exe -m app.persistence.backup_cli backup `
  --data-dir ..\data `
  --backup-root "$env:USERPROFILE\TheraSimBackups"
```

The operational database also contains the local account's password hash and
bearer-session metadata. Encrypted backups protect backup copies only; the
live SQLite databases remain unencrypted at rest. Protect live data with
Windows filesystem permissions and device encryption.

## Restore to a new directory

Restore validates the manifest, checksums, authentication tags (for encrypted
backups), and SQLite integrity before publishing any files. Encrypted backups
prompt for their passphrase. Restore refuses to overwrite an existing
destination:

```powershell
..\.venv\Scripts\python.exe -m app.persistence.backup_cli restore `
  "$env:USERPROFILE\TheraSimBackups\therasim-backup-20260102T030405.000000Z" `
  "$env:USERPROFILE\TheraSim-restored-data"
```

Restore into a new directory first. Review its contents and configure
`THERASIM_DATA_DIR` to use it only after confirming the recovered data. Never
restore over an active or existing user data directory during development.

## Retention

TheraSim does not automatically delete or rotate backups. Choose and document a
retention period appropriate for the research project, securely remove expired
copies, and test restoration periodically using a separate destination.
