# Installation

TheraSim is a local-first research and educational prototype. The backend and
browser interface can run without a model provider; AI-assisted workflows need
a separately installed provider and model. No model weights are bundled.
Local-first describes the default deployment, not an air-gap guarantee.

## Windows portable package

For the supported packaged workflow, use the Windows x64 ZIP and its matching
SHA-256 sidecar from the [GitHub Releases page](https://github.com/mohammadmahdialmasi/TheraSim/releases)
only after the release's Windows workflow has passed. Verify the checksum
before extracting, then follow [Install on Windows](../INSTALL_WINDOWS.md).
The portable ZIP contains an application directory; it is not an installer or
a single-file executable. It requires no administrator access.

Application data is stored separately under `%LOCALAPPDATA%\TheraSim`, so
replacing the extracted application directory does not replace the databases,
settings, or logs. Back up the data directory before upgrading or moving the
application. The packaged application binds to loopback; do not expose it to a
network without first designing and reviewing an appropriate security model.

## Run from source

Use the Python and Node.js versions and locked dependencies documented in
[BUILD_WINDOWS.md](../BUILD_WINDOWS.md) for a reproducible Windows build. For
development, install the backend dependencies from
[`backend/requirements-lock.txt`](../backend/requirements-lock.txt), install
the frontend dependencies with `npm ci` in `frontend/`, and follow the
repository's development scripts and environment examples. Keep local
configuration and databases out of source control.

## Configure a local model

Install Ollama or another supported OpenAI-compatible provider separately.
See the English [Ollama setup guide](OLLAMA_SETUP.md) or
[Persian Ollama setup guide](OLLAMA_SETUP.fa.md). In Settings, configure the
provider endpoint and model. Patient and evaluator model IDs can be set
separately; either can fall back to the provider's general model. Restart the
application after changing provider/model settings when prompted.

Use only fictional data. Verify the configured endpoint before sending any
text: a user-selected remote endpoint can receive prompts if local-only
restrictions are explicitly disabled and remote use is confirmed.

## Language and support

The interface supports English and Persian. The settings page offers a
user-reviewed diagnostics preview/export; inspect the preview before saving or
sharing it. Support export is allow-listed and does not include database files,
transcripts, scenario text, credentials, or configured endpoints. The export
does not send itself.

For data handling and backup instructions, see
[Backup and restore](BACKUP_RESTORE.md). For system boundaries and security
assumptions, see [Security boundaries](SECURITY_BOUNDARIES.md).
