# TheraSim Installation and Runtime Specification

**Document ID:** THERASIM-INSTALL-RUNTIME-001
**Version:** 0.1
**Status:** Architecture Draft
**Target Platform:** Windows x64
**Installer:** TheraSim-Setup.exe
**Last Updated:** 2026-11-16

---

## 1. Purpose

This document defines the installation, dependency management, application startup, and runtime lifecycle of TheraSim Windows Desktop.

The installation experience must be graphical and suitable for non-technical end users.

The user must be able to install TheraSim using one installer executable without manually installing Python, Node.js, Git, or project dependencies.

## 2. Installation Requirements

The initial release must provide:

- One Windows installer executable.
- Graphical installation wizard.
- Per-user installation.
- Automatic installation of required bundled dependencies.
- Automatic application directory creation.
- Automatic user-data directory creation.
- Desktop shortcut.
- Start Menu shortcut.
- Uninstaller.
- Clear installation error messages.
- No requirement for administrator privileges during normal per-user installation.

Target installer filename: TheraSim-Setup.exe

## 3. Installer Technology

The proposed installer technology is Tauri 2 with the NSIS bundler.

Selected installation mode: currentUser.

Proposed installation directory:

%LOCALAPPDATA%\Programs\TheraSim\

The installer should not request administrator privileges for normal per-user installation.

System-wide installation is outside the initial release scope.

## 4. Required Runtime Components

The installer must include all application-specific components required for normal operation.

| Component | Distribution Strategy |
|---|---|
| Desktop application | Included in installer |
| React frontend | Bundled application resources |
| FastAPI backend | Standalone executable |
| Python dependencies | Bundled with backend |
| Python interpreter | Bundled through backend packaging |
| Tauri runtime | Included in desktop application |
| WebView2 Runtime | Installer dependency |
| SQLite | Python standard library |

The end user must not be required to install Python, Node.js, npm, Git, Rust, or project dependencies.

Development tools are required only in development and release environments.

## 5. WebView2 Dependency

Tauri uses Microsoft Edge WebView2 to render its Windows interface.

The initial installer should support installation without requiring an internet connection.

Proposed configuration: WebView2 offline installer.

The installer must verify whether the required WebView2 Runtime is available and install it when necessary.

The Evergreen Runtime is preferred over a fixed-version runtime for the initial release.

The additional installer size and final compatibility requirements must be evaluated before the first public release.

## 6. External Inference Providers

Ollama and LM Studio are external inference providers.

They are optional dependencies and are not mandatory installation components.

The TheraSim installer must not silently install large language models or external inference applications.

During first launch, the application may:

- Detect an available Ollama service.
- Detect a configured LM Studio endpoint.
- Display provider connection status.
- Guide the user through provider configuration.
- Explain when no local inference provider is available.

The absence of an inference provider must not prevent the desktop application itself from starting.

Model downloads and provider installations must require explicit user action.

## 7. Application Installation Directory

Proposed application directory:

%LOCALAPPDATA%\Programs\TheraSim\

Expected logical structure:

- TheraSim.exe
- runtime/
- runtime/backend/
- resources/
- resources/frontend/
- resources/assets/
- updater/

The actual generated file structure will depend on Tauri and PyInstaller packaging configuration.

Application installation files must be treated as replaceable release artifacts.

## 8. Persistent User Data Directory

Proposed persistent data directory:

%LOCALAPPDATA%\TheraSim\

Expected logical structure:

- data/therasim.db
- data/case_vault.db
- config/
- logs/
- backups/
- models/
- exports/

This directory must remain separate from the application installation directory.

The application must create required directories automatically.

The application must never assume that its installation directory is writable for persistent user data.

## 9. Installation Wizard

The installation process must be graphical.

Expected installation stages:

1. Welcome screen.
2. License and usage information.
3. Installation location.
4. System compatibility checks.
5. WebView2 Runtime verification and installation when necessary.
6. Application file installation.
7. Shortcut creation.
8. Installation completion.
9. Optional immediate application launch.

The installer must display meaningful progress and errors.

The user must not need to interact with a terminal.

The installer must not initialize or overwrite an existing user database.

## 10. First Application Launch

On the first launch:

1. The desktop shell initializes.
2. The user-data directory is checked and created.
3. Application configuration is loaded or initialized.
4. The backend executable is located.
5. The backend process is started.
6. The backend receives its runtime configuration.
7. The backend initializes its DatabaseManager.
8. Operational and restricted databases are independently initialized.
9. Existing migrations are verified and pending migrations are applied.
10. Backend health is checked.
11. The frontend is allowed to access the application.

The application must not report readiness before successful backend initialization.

First-run initialization must be repeatable and safe.

## 11. Backend Runtime Management

The desktop shell is responsible for backend process lifecycle.

The runtime manager must support:

- Process startup.
- Backend readiness checks.
- Startup timeout.
- Health monitoring.
- Unexpected process termination detection.
- Graceful shutdown.
- Controlled forced termination after a timeout.
- Diagnostic logging.

The backend must run without exposing an unnecessary terminal window.

The backend must bind exclusively to the loopback interface.

A controlled local port and protected short-lived session token must be used for desktop communication.

The session token must not be exposed in ordinary logs.

The frontend must not communicate with SQLite directly.

## 12. Startup Failure Handling

If the backend fails to start:

- The desktop shell must not display a false ready state.
- A user-readable error must be displayed.
- Relevant diagnostic details must be written to local logs.
- Sensitive data and authentication tokens must be excluded from logs.
- The user must be able to access diagnostic information.

If database initialization fails, the application must not silently create a new empty database in place of an existing database.

Database recovery must follow the separate backup and recovery specification.

## 13. Application Shutdown

When the user exits TheraSim:

1. New operations are rejected or safely deferred.
2. Active application operations are handled according to their interruption policy.
3. The backend receives a graceful shutdown request.
4. The backend process is monitored during shutdown.
5. A bounded timeout is applied.
6. The process is terminated only if graceful shutdown fails.

The application must not intentionally terminate a process before its persistence operations have reached a safe boundary.

## 14. Uninstallation

The uninstaller must remove application installation files and application shortcuts.

The uninstaller must not silently delete:

- Operational database.
- Restricted database.
- User configuration.
- Backups.
- Exported files.
- User-managed local models.

User-data deletion must be a separate explicit action with a clear warning.

Uninstallation must not mean automatic database deletion.

## 15. Installation and Runtime Logging

The application must provide diagnostic logs for:

- Installation failures.
- Runtime initialization.
- Backend startup.
- Backend health failures.
- Database initialization errors.
- Application shutdown.

Logs must not contain:

- Authentication tokens.
- Passwords.
- Private signing keys.
- Unnecessary restricted case information.
- Full sensitive conversation contents by default.

Logs must have a retention and size-management policy.

## 16. Development and Release Build Requirements

The release build environment will use the required development tools.

These may include:

- Node.js and npm.
- Rust toolchain.
- Tauri CLI.
- Python.
- PyInstaller.
- Backend test dependencies.
- NSIS build tooling as required by Tauri.

These tools are build-time dependencies and must not be required on the end user's computer.

The release pipeline must package the frontend, backend, and required runtime components into the installer.

## 17. Acceptance Criteria

The installation implementation will not be considered complete until these tests pass:

1. Installation on a clean supported Windows environment.
2. Installation without Python.
3. Installation without Node.js.
4. Installation without Git.
5. Successful installation of required WebView2 Runtime when absent.
6. Successful first-run database initialization.
7. Successful application launch without opening a terminal.
8. Preservation of databases after application restart.
9. Preservation of user data after application update.
10. Preservation of user data after ordinary uninstallation.
11. Correct error reporting when backend startup fails.
12. Successful application shutdown without database corruption.

## 18. Implementation Status

This document records the intended installation and runtime architecture.

The following components are planned and not yet implemented:

- Tauri desktop shell.
- Backend executable packaging.
- Desktop runtime manager.
- Windows installer.
- WebView2 installation integration.
- Application startup diagnostics.
- Installation and runtime integration tests.

Implementation must proceed after architecture review and completion of the relevant contracts.

The repository now includes a Windows source-development launcher
(`START_THERASIM.bat`) with a companion stop and prerequisite-check command.
It runs the existing Python and Vite development servers and preserves user
databases. It is not the Tauri desktop shell, installer, or a packaged
production runtime, and clean-machine installation has not been verified.
