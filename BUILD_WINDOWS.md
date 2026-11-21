# Build the Windows package

This repository provides a Windows **one-folder portable package**, not an
installer. It runs the local FastAPI service on loopback and opens the bundled
React interface in the default browser. It installs no Windows service,
requires no administrator rights, bundles no model weights, and does not
provide an air-gapped dependency installation.

## Requirements

- Windows 10/11 x64
- Python 3.13 x64 and a virtual environment
- Node.js 22 LTS and npm
- Internet access for the first dependency installation

The versions of application and packaging dependencies are pinned in
`backend/requirements-lock.txt`, `frontend/package-lock.json`, and
`packaging/windows/requirements-build.txt`.

## Build

From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\scripts\build-windows.ps1
```

The build runs `npm ci`, frontend lint and TypeScript/production build, installs
the pinned backend/build dependencies, then creates a PyInstaller one-folder
package. The default output is
`dist\TheraSim-v0.3.1-Windows-x64-Portable.zip`, accompanied by a SHA-256
sidecar and JSON build manifest. The manifest records the artifact name, version,
architecture, package format, build-runtime versions, byte size, checksum,
and that model weights are excluded.
Existing output files are never overwritten. The temporary build directory is
removed after success or failure. Build from a clean checkout when preparing a
public release. The migration bundle includes only `.sql` files from the
operational and restricted migration directories; archive verification
rejects backup files and mismatches against that source allowlist.

To select another Python executable or output path:

```powershell
.\scripts\build-windows.ps1 `
  -PythonExe .\.venv\Scripts\python.exe `
  -OutputZip "$env:TEMP\TheraSim-v0.3.1-Windows-x64-Portable.zip"
```

## Verify the actual package

Run the smoke test against the resulting archive:

```powershell
.\scripts\verify-windows-package.ps1 `
  -PackageZip .\dist\TheraSim-v0.3.1-Windows-x64-Portable.zip
```

The smoke test extracts the package into a unique temporary directory,
redirects `LOCALAPPDATA` to that directory, launches the executable, checks the
health endpoint and bundled web interface, and initializes one synthetic
reviewer account in a temporary SQLite database. It never reads or uses the
current user's TheraSim database. The test removes only its own temporary
directory, disables automatic browser launch, removes Python/Node-specific
environment variables, uses a system-only `PATH`, restarts the application to
check persisted synthetic account initialization, and verifies its listener
and process have stopped. Shutdown is forced; graceful shutdown is not tested.
To additionally verify a locally installed Ollama model and one
synthetic chat, run:

```powershell
.\scripts\verify-windows-package.ps1 `
  -PackageZip .\dist\TheraSim-v0.3.1-Windows-x64-Portable.zip `
  -TestOllama `
  -OllamaModel "gemma-4-E2B:latest"
```

That optional check requires Ollama to already be running on `127.0.0.1:11434`
with the exact model tag installed. It does not download model weights.

The executable keeps a console open for startup errors and logs to
`%LOCALAPPDATA%\TheraSim\logs\therasim.log`. See
[`INSTALL_WINDOWS.md`](INSTALL_WINDOWS.md) for user installation and data
handling. A successful build or smoke test is not a clinical or security
validation.
