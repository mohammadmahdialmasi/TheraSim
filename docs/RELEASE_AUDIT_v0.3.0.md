# TheraSim v0.3.0 — Release audit

**Audit date:** 2026-11-21
**Version metadata:** 0.3.0
**Artifact:** `TheraSim-v0.3.0-Windows-x64-Portable.zip`

This report records local source and package evidence. A GitHub release is
authoritative only when its assets and workflow status are visible on the
official [GitHub Releases page](https://github.com/mohammadmahdialmasi/TheraSim/releases).
This audit is not clinical, psychometric, independent security, or clean-device
validation.

## Package evidence

The package was freshly built from the current source on Windows 11 Pro x64
using Python 3.13.9 and Node.js 26.13.0. It is a PyInstaller one-folder
application inside a ZIP, not an installer or single-file executable. The
build script refused to overwrite existing output; the fresh package was
written into a new temporary directory.

| Property | Value |
|---|---|
| File | `TheraSim-v0.3.0-Windows-x64-Portable.zip` |
| Size | 26,345,293 bytes |
| SHA-256 | `df1be242f0040b67b9b15ad7e7d7f52e136ed260f690f79370716200d9715319` |
| Package format | Windows x64 portable one-folder ZIP |
| Model weights | Not included |
| Manifest and sidecar | Both match the archive checksum |

Archive inspection found 1,110 entries under one top-level `TheraSim/`
directory, including 19 allow-listed SQL migrations. No SQLite database,
database sidecar, backup, `.env`, provider-settings file, key, or model weights
were present. No absolute or parent-traversal archive paths were detected.

The fresh extraction smoke test passed on the same development workstation:

- packaged executable started with a system-only `PATH` and served the local
  health endpoint and UI;
- a synthetic local reviewer account was initialized in isolated temporary
  application data and persisted across restart and replacement-directory
  extraction;
- the process completed graceful shutdown and left no listener;
- the packaged app connected to the already-installed local Ollama
  `qwen2.5:3b` model and completed one fictional synthetic chat.

No existing user database or patient data was read. The Ollama check is a
generic local chat smoke test, not a PatientAgent benchmark or ACT evaluator
validation. No clean VM or physically disconnected network was used.

## Software and dependency checks

- Backend: 507 tests passed with Python 3.13.9.
- Frontend: 18 tests passed; ESLint, TypeScript, and Vite production build
  passed.
- `pip-audit` found no known vulnerabilities in the backend lock or Windows
  packaging requirements at scan time.
- Full `npm audit --audit-level=moderate` reported zero vulnerabilities.
- Bandit reported 11 findings: 0 high, 6 medium, and 5 low. SQL-fragment
  construction, a fixed HTTPS release URL, and bounded subprocess use were
  reviewed; findings remain visible and are not suppressed. See
  [Security audit](SECURITY_AUDIT.md).

## Model and device scope

Current workstation inventory: Windows 11 Pro build `10.0.26300`, 15.6 GiB
visible RAM, Intel Core i7-12650H (10 cores / 16 logical processors), NVIDIA
RTX 3060 Laptop GPU with 6 GiB VRAM, and Intel UHD graphics. This is one
machine, not a general compatibility claim.

Synthetic `qwen2.5:3b` PatientAgent tests recorded 7/7 schema-valid responses.
Its ACT EvaluatorAgent passed 4/6 repeated reports; two were rejected for
failing exact transcript-quote validation. Two additional structured reports
passed, but reliability is not established. No evaluator model is recommended.
The application still validates evaluator reports, rubric coverage, transcript
speakers/messages, and exact quotes; structured output does not bypass those
checks. See [local model evaluation](LOCAL_AI_MODEL_EVALUATION.md) and
[`config/model-compatibility.json`](../config/model-compatibility.json).

## Security, privacy, and research boundaries

- SQLite databases are not encrypted at rest. The local reviewer account is
  not multi-user authorization or password recovery.
- Saved Windows provider keys use DPAPI for the current Windows user.
  Persistent provider-key storage is not supported on non-Windows platforms;
  use environment variables there.
- User-selected remote providers may receive submitted text after local-only
  controls are explicitly disabled and remote use is confirmed. Use fictional
  data only.
- Support export is allow-listed, previewed, user-confirmed, and not
  automatically sent. Update checking reads official stable-release metadata
  but does not install or overwrite files.
- ACT is the only runnable modality. Clinical, therapeutic, psychometric,
  evaluator, rubric, analytics, and simulated-response validity have not been
  established.
- No penetration test or independent security review was performed. Bandit
  findings and residual trust assumptions remain documented.

## Publication boundary

The package evidence above does not itself publish or authorize a release.
Before users download v0.3.0, verify that the official GitHub release contains
the expected ZIP and matching `.sha256` sidecar and that its Windows workflow
completed successfully. Do not substitute any pre-existing local `dist/`
archive for the freshly verified artifact.
