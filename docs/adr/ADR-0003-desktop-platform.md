# ADR-0003: Windows Desktop Platform and Distribution

**ADR ID:** ADR-0003
**Status:** Proposed
**Date:** 2026-11-16
**Decision Scope:** Initial Desktop Distribution
**Target Platform:** Windows x64

---

## 1. Context

TheraSim is currently developed as a local-first application with:

- FastAPI backend.
- React and TypeScript frontend.
- SQLite operational database.
- Separate restricted case database.
- Local inference providers such as Ollama and LM Studio.

The current development environment requires separate backend and frontend tooling.

The initial public release must provide a graphical Windows installation experience that does not require end users to install development tools or execute terminal commands.

The desktop architecture must preserve the existing simulation, persistence, and security boundaries.

Application installation and application updates must not destroy user data.

## 2. Decision Summary

The proposed initial desktop distribution architecture is:

| Concern | Selected Direction |
|---|---|
| Target platform | Windows x64 |
| Desktop framework | Tauri 2 |
| Frontend | Existing React + TypeScript |
| Backend | Existing FastAPI |
| Backend packaging | PyInstaller onedir |
| Backend lifecycle | Desktop-managed process |
| Installer | Tauri NSIS |
| Installation mode | Per-user |
| Persistent data | Local application data directory |
| Update distribution | GitHub Releases |
| Update mechanism | Tauri Updater |
| Database | Existing independent SQLite databases |

These decisions define the intended architecture. Exact versions and integration details require technical validation before implementation.

## 3. Decision 1: Windows First

The initial desktop release will target Windows x64.

A single installer executable will be distributed:

TheraSim-Setup.exe

Linux and macOS are outside the initial release scope.

The application domain and persistence layers must not depend on Windows-specific functionality.

Future platform support should be possible by replacing or extending the desktop integration layer.

## 4. Decision 2: Tauri Desktop Shell

Tauri 2 is selected as the proposed desktop application framework.

Responsibilities include:

- Native application window.
- Desktop application lifecycle.
- Backend process management.
- Controlled communication between desktop and backend.
- Application resource access.
- Update integration.
- Desktop installation packaging.

The desktop shell must not contain simulation domain logic.

The existing React frontend will be retained.

The existing FastAPI backend will remain responsible for application and simulation services.

## 5. Decision 3: Standalone Backend Packaging

The existing Python backend will initially be packaged using PyInstaller onedir.

The resulting executable and its required dependencies will be distributed with the desktop application.

The desktop runtime manager will be responsible for starting, monitoring, and stopping the backend process.

The exact packaging layout will be established through a Windows build prototype.

The end user must not be required to install:

- Python.
- pip packages.
- Node.js.
- npm.
- Git.
- Rust.
- Uvicorn.

These tools remain development and release-build dependencies.

## 6. Decision 4: NSIS Per-User Installation

The initial installer will use the Tauri NSIS bundler.

The selected installation direction is per-user installation.

Proposed application directory:

%LOCALAPPDATA%\Programs\TheraSim\

The installer must provide:

- Graphical setup.
- Installation progress.
- Application shortcuts.
- Start Menu entry.
- Uninstallation support.
- Clear failure messages.

A portable distribution and system-wide installation are outside the initial release scope.

## 7. Decision 5: WebView2 Runtime

The Windows desktop application requires Microsoft Edge WebView2.

The installer must detect whether a compatible WebView2 Runtime is available.

If it is absent, the installer must provide an installation path for the required runtime.

Offline installation is an objective for the initial installer.

The exact Tauri WebView2 installation configuration and its effect on installer size must be validated in a working prototype.

The Evergreen Runtime is preferred over maintaining a fixed WebView2 runtime version.

## 8. Decision 6: Application Data Separation

Application installation files and persistent user data must remain separate.

Application installation:

%LOCALAPPDATA%\Programs\TheraSim\

Persistent user data:

%LOCALAPPDATA%\TheraSim\

The persistent directory may contain:

- Operational database.
- Restricted database.
- Application configuration.
- Logs.
- Backups.
- Local models.
- User exports.

The application installation directory must never be used as the primary persistent data location.

Updates and ordinary uninstallation must preserve user data.

Deleting user data must require an explicit user decision.

## 9. Decision 7: Database Lifecycle

The existing automatic FastAPI database initialization will remain responsible for database creation and migrations.

The operational and restricted SQLite databases will retain separate migration histories.

The desktop shell must prepare the persistent data directory before backend startup.

The backend must not report readiness until database initialization and required validation are complete.

Database files must never be distributed as pre-populated user databases.

Database backup and recovery must be coordinated before update-related migrations.

## 10. Decision 8: Local Backend Communication

The backend will be accessible only through a local communication boundary.

Mandatory constraints:

- Bind exclusively to loopback.
- Use controlled local port allocation.
- Authenticate desktop-originated requests.
- Protect runtime credentials.
- Avoid exposing authentication secrets in logs.
- Reject unauthorized requests.
- Shut down with the desktop application.

The frontend must not access SQLite files directly.

The frontend must not receive unrestricted backend credentials.

The preferred integration is a controlled desktop bridge or an equivalently protected communication design.

The exact IPC and authentication protocol requires a dedicated technical specification before implementation.

## 11. Decision 9: GitHub Release Updates

Official application releases will be distributed through GitHub Releases.

The proposed update mechanism is the official Tauri 2 Updater integration.

Updates must use versioned release artifacts.

The application must not use git pull or execute code directly from the main development branch.

The updater must verify cryptographic signatures before accepting an update.

The signing private key must remain outside the source repository and installed application.

Stable is the initial release channel.

A Beta channel may be introduced later.

## 12. Decision 10: Installer and Updater Artifacts

The ordinary Windows installer and the Tauri updater package are treated as distinct release artifacts.

The expected NSIS updater artifact follows the Tauri-generated archive and signature format.

The release pipeline must use the actual artifacts produced by the selected Tauri build configuration.

The update manifest must reference the correct updater archive and contain its generated signature.

Artifact filenames and signature values must never be guessed or manually invented.

## 13. Decision 11: Backup and Recovery

The update architecture must preserve both SQLite databases as a coordinated recovery unit.

Before a migration:

1. Prevent conflicting database writes.
2. Create verified backups of both databases.
3. Record application and schema versions.
4. Apply migrations independently.
5. Validate database integrity.
6. Restore both databases when coordinated recovery is required.

The system must not assume that independent SQLite databases share one atomic transaction.

Automatic rollback of application binaries must be designed separately from database recovery.

## 14. Decision 12: Local Inference Providers

Ollama and LM Studio remain optional external inference providers.

The installer must not silently install these applications or download large language models.

Provider availability must be checked and configured through the application interface.

The absence of a provider must not prevent the desktop shell from starting.

Normal application operation must not depend on GitHub connectivity.

## 15. Alternatives Considered

### Electron

Not selected for the initial implementation.

The project will first evaluate Tauri because the existing frontend can be retained while the desktop integration layer manages the Python backend independently.

### Browser-Based Distribution

Not selected as the final distribution model.

A native desktop installer is required for the intended end-user experience and lifecycle management.

### Direct Python Installation

Not selected for end-user distribution.

Requiring users to install Python and manually configure project dependencies would make installation unnecessarily complex.

### Git-Based Updating

Rejected.

End users must receive signed, versioned application releases rather than source repository changes.

## 16. Consequences

Expected benefits:

- Single graphical Windows installer.
- No manual Python or Node.js installation.
- Existing React frontend retained.
- Existing FastAPI backend retained.
- Local-first application operation.
- Versioned GitHub updates.
- Separation of installation files and user data.
- Controlled application lifecycle.

Expected engineering costs:

- Rust and Tauri development tooling.
- Windows desktop integration.
- Backend executable packaging.
- Installer configuration.
- WebView2 dependency handling.
- Update signing and release automation.
- Backup and recovery implementation.
- Additional desktop integration tests.

## 17. Deferred Technical Decisions

The following details require validation before implementation:

- Exact Tauri release version.
- Exact Rust toolchain version.
- Minimum supported Windows version.
- Exact WebView2 offline installation configuration.
- PyInstaller packaging and resource layout.
- Backend process supervision strategy.
- Local IPC and authentication protocol.
- NSIS installer configuration.
- Update signing and secret-management procedure.
- Database backup retention policy.
- Application binary rollback strategy.
- GitHub Actions release permissions.

Deferred decisions must be documented before the relevant implementation begins.

## 18. Implementation Sequence

The implementation sequence is:

1. Complete Service Layer architecture.
2. Define application configuration and data paths.
3. Stabilize backend application startup and shutdown contracts.
4. Define desktop-to-backend communication.
5. Build a minimal Tauri technical prototype.
6. Package the existing backend as a standalone executable.
7. Integrate the React frontend.
8. Implement Windows installation.
9. Implement update and recovery functionality.
10. Automate signed GitHub Releases.
11. Perform clean-machine installation and update testing.

Desktop integration must not bypass existing backend persistence and security boundaries.

## 19. Status and Review

This ADR records the proposed Windows desktop distribution direction.

It does not indicate that Tauri, PyInstaller, NSIS, or the updater have already been implemented or successfully integrated.

Technology-specific decisions remain subject to a working proof of concept.

The ADR must be revised if implementation evidence requires a different architecture.

---

**Related Documents:**

- docs/architecture/DESKTOP_DISTRIBUTION_SPEC.md
- docs/architecture/INSTALLATION_AND_RUNTIME_SPEC.md
- docs/architecture/UPDATE_AND_RECOVERY_SPEC.md
- docs/adr/ADR-0001-sqlite-persistence.md
- docs/adr/ADR-0002-domain-persistence.md
