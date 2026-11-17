# TheraSim Desktop Distribution Specification

**Document ID:** THERASIM-DESKTOP-DIST-SPEC-001
**Version:** 0.1
**Status:** Architecture Draft; portable implementation differs from this
initial installer/Tauri direction
**Target:** Windows x64
**Last Updated:** 2026-11-16

## 1. Purpose

This document defines the architecture for distributing TheraSim as an independently installable Windows desktop application.

The end user must not need to manually install Python, Node.js, Git, or project dependencies.

## 2. Initial Distribution Decisions

**Current implementation status:** the current executable is a PyInstaller
one-folder Windows portable package, not an MSI or NSIS installer. The Tauri
and installer descriptions below remain planned architecture and are not
implemented as a release workflow for the portable package.

- Operating system: Windows 10/11 x64.
- Distribution format: Single installer executable.
- Installer filename: TheraSim-Setup.exe.
- Installation mode: Per-user.
- Portable version: Out of scope for the first release.
- Normal operation: Local-first.
- Application updates: GitHub Releases.
- User data: Stored separately from application files.

Future Linux and macOS support should remain architecturally possible.

## 3. Technology Direction

| Component | Technology | Responsibility |
|---|---|---|
| Desktop shell | Tauri 2 | Native desktop application |
| Frontend | React + TypeScript | User interface |
| Backend | FastAPI | Application logic and API |
| Backend packaging | PyInstaller | Standalone executable |
| Database | SQLite | Local persistence |
| Windows installer | NSIS | Application installation |
| Update distribution | GitHub Releases | Versioned releases |
| Update mechanism | Tauri Updater | Application updates |

Technology versions must be verified before implementation.

## 4. Application Architecture

The desktop application will contain:

1. Desktop Shell
2. Frontend Application
3. Backend Runtime Manager
4. Backend Executable
5. Local API Communication Layer
6. Application Configuration
7. Update Manager
8. Backup and Recovery Manager

The desktop layer must remain separate from simulation domain logic.

The backend and frontend must remain independently testable.

## 5. Backend Runtime

The existing FastAPI backend will be packaged as a standalone executable.

Initial packaging direction: PyInstaller onedir.

The desktop application must manage:

- Backend startup.
- Backend readiness checks.
- Backend health monitoring.
- Startup failure handling.
- Graceful backend shutdown.

The end user must not need to run Python or Uvicorn commands.

## 6. Local Communication and Security

The backend must:

- Listen only on the loopback interface.
- Use a controlled local port.
- Authenticate local requests using a protected, short-lived session token.
- Reject unauthorized requests.
- Avoid writing authentication tokens to logs.
- Shut down when the desktop application exits.

The local backend must not become a publicly accessible network service.

The frontend must not access SQLite files directly.

## 7. Installation and User Data

Proposed per-user application installation path:

`%LOCALAPPDATA%\Programs\TheraSim\`

Persistent user-data path:

`%LOCALAPPDATA%\TheraSim\`

The user-data directory may contain:

- data/therasim.db
- data/case_vault.db
- config/
- logs/
- backups/
- models/
- exports/

Application files and user data must remain separate.

Uninstalling or updating the application must not silently delete user data.

User data deletion must require explicit user confirmation.

## 8. Database Initialization

The existing automatic FastAPI startup initialization remains responsible for creating and migrating the databases.

On first launch:

1. Prepare the user-data directory.
2. Initialize the operational database.
3. Initialize the restricted database independently.
4. Apply the applicable migrations.
5. Verify database integrity.
6. Report backend readiness.

Database files are runtime artifacts. They must not be committed to Git or distributed as pre-populated user databases.

The two databases must retain independent migration histories.

## 9. Local-First Operation

Normal application operation must not depend on GitHub or an external application server.

Internet connectivity is only required for optional operations such as checking and downloading updates.

Failure to connect to GitHub must not prevent an otherwise functional local installation from starting.

Local inference providers such as Ollama and LM Studio remain independently configurable.

## 10. Update Architecture

Application updates will be distributed through versioned GitHub Releases.

The update mechanism must:

- Check the configured release channel.
- Compare installed and available versions.
- Display release notes.
- Download official release artifacts.
- Verify cryptographic signatures.
- Reject invalid or incomplete updates.
- Preserve user data.
- Support recovery from failed updates.

The application must never use git pull or execute arbitrary code from the repository's development branch as an update mechanism.

The private signing key must never be included in the repository, installer, or installed application.

## 11. Backup and Recovery

Before database migrations:

1. Ensure no conflicting database operation is active.
2. Create backups of both databases.
3. Record the current schema versions.
4. Apply migrations.
5. Verify database integrity.
6. Restore both databases if the coordinated migration process fails.

The operational and restricted databases must be treated as one coordinated recovery unit, while retaining independent migration histories.

## 12. Release Pipeline

The intended release process is:

1. Create a versioned Git tag.
2. Run backend tests.
3. Run frontend lint and build checks.
4. Package the backend executable.
5. Build the frontend.
6. Build the Tauri application.
7. Generate the Windows installer.
8. Sign release artifacts.
9. Generate update metadata.
10. Publish a GitHub Release.

Release builds must be traceable to a source revision.

Signing credentials must be stored securely in the release environment.

## 13. Initial Release Exclusions

The following are excluded from the first release:

- Linux installer.
- macOS installer.
- Portable distribution.
- Automatic installation of large language models.
- Cloud-hosted database.
- Mandatory online account.
- Git repository management by end users.
- Automatic synchronization of user data to GitHub.

## 14. Mandatory Architectural Constraints

1. Desktop code must remain separate from simulation domain logic.
2. Backend and frontend must remain independently testable.
3. User databases must remain outside the application installation directory.
4. Updates must preserve user data.
5. Database migrations must remain independently versioned.
6. Update signatures must be verified.
7. Normal operation must remain local-first.
8. Private signing credentials must never be committed.
9. Existing persistence and security boundaries must be preserved.

## 15. Implementation Status

This document records the intended architecture.

The following components are planned and not yet implemented:

- Tauri desktop shell.
- Backend executable packaging.
- Desktop runtime manager.
- Windows installer.
- Update manager.
- Signed GitHub update releases.
- Backup and recovery integration.
- Desktop integration tests.
