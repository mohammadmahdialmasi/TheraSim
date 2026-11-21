# Security Audit

**Review date:** 2026-11-21
**Scope:** source inspection, focused regression tests, dependency audits, and
a limited tracked-text secret-pattern check. No penetration test or
independent security review was performed. This document does not assert that
TheraSim is secure or vulnerability-free.

## Findings and current controls

| Area | Source-visible behavior / control | Residual risk |
|---|---|---|
| Network binding | The Windows launcher binds Uvicorn to `127.0.0.1`, defaults to port 8765, and checks port availability. | Other development launch methods and local malware are outside this boundary. Loopback is not a substitute for host security. |
| Authentication | One local reviewer account uses salted `hashlib.scrypt`; bearer tokens are cryptographically random, expire, and are stored as SHA-256 digests. Login throttling is persisted. Protected API routes depend on the current-user check. | No multi-user roles, account recovery, or defense against a compromised local user account. |
| Provider URLs | HTTP(S) URLs are parsed and validated; user-info/query/fragment are rejected; non-loopback HTTP is rejected. Local-only mode defaults on and blocks remote endpoints. Turning it off requires explicit remote-endpoint confirmation. | A user-confirmed remote HTTPS endpoint receives prompts/transcripts sent to it. TLS does not establish the provider's data-handling practices. |
| Provider credentials | Windows-saved keys use DPAPI for the current user; API responses expose only a configured/not-configured flag. Legacy plaintext keys are migrated on Windows. | DPAPI does not protect against a process running as the same user. Live SQLite data is not encrypted. Persistent provider-key storage is not supported on non-Windows systems. |
| SQL access | Persistence uses SQLite parameters/repositories and fixed database names; migrations are checksum-verified and use explicit transaction management. | The report is source inspection plus tests, not exhaustive SQL-injection analysis. |
| Static file routing | Packaged SPA paths are resolved and checked to stay beneath the static root before serving. | Other filesystem/export paths still need their own authorization and path checks; do not extrapolate this guard to every feature. |
| Support export | Export uses a purpose-built diagnostics report and a strict data-minimized schema; it does not export databases, case content, transcripts, or provider credentials. The UI requires review/confirmation and sends nothing automatically. | A user may manually attach an archive to an external message. Inspect generated diagnostics before sharing. |
| Backup/restore | Paired DB backups are verified; optional encryption uses established cryptography (scrypt KDF and authenticated encryption); restore refuses overwrite of an existing destination. | Unencrypted live DBs and ordinary backups remain readable to the OS account. Keep passphrases safe; they cannot be recovered. |
| Updates | Release metadata is read-only and validates stable release/digest details; the feature does not run Git or install files. | It is not automatic installation or signed-update verification. Users must verify downloads and use a trusted source. |
| Logs | Desktop log files rotate and errors are reported. Provider request errors avoid rendering API-key values. | Logs remain local files and must be treated as potentially sensitive; do not attach raw logs without review. |
| Packaging | Windows package uses explicit resources and excludes model weights; runtime data is kept outside the extracted app directory. | Package smoke tests on this workstation do not establish clean-machine security or reproducibility on every Windows version. |
| Hardware assessment | Hardware inventory is opt-in through an authenticated endpoint. It reads OS/CPU/RAM/disk data, queries NVIDIA only through `nvidia-smi`, and probes an Ollama API version only on a loopback URL. No model is downloaded or selected. | Intel/AMD GPU inventory is not implemented. `nvidia-smi` is resolved through `PATH`; a compromised `PATH` could execute an unintended binary. The estimate does not establish model fit. |

## Verification run

- Backend test suite: **507 passed**.
- Frontend tests: **18 passed**; ESLint and TypeScript/Vite production build
  passed.
- `pip-audit` against `backend/requirements-lock.txt` and
  `packaging/windows/requirements-build.txt`: **no known vulnerabilities**
  reported at scan time.
- Full `npm audit --audit-level=moderate`: **zero vulnerabilities** reported
  at scan time.
- Bandit 1.9.2 over `backend/app`: **11 findings** (0 high, 6 medium, 5 low).
  There are five B608 SQL-construction warnings. Review found bound values and
  constrained internal SQL fragments (fixed column/assignment names,
  parameter placeholders, or internally generated `?` placeholders). The
  B310 warning is the fixed official HTTPS update-metadata URL, not a
  user-controlled URL. B404/B603/B607 warnings relate to bounded subprocess
  calls with argument arrays and no shell; `nvidia-smi` and `git` are resolved
  through `PATH`, which remains a host trust assumption. These findings remain
  visible and were not suppressed. Bandit exits nonzero when reporting them.
- `detect-secrets` scanned **761 unique reachable Git-history blobs across 93
  reachable commits**, with no large blobs skipped and **zero findings**.
  The slow initial scan was stopped and replaced with a single batched
  `git cat-file` scan; the batched scan completed successfully.
- `detect-secrets` 1.5.0 scanned the publication file list with network
  verification disabled. It reported nine candidates: a Windows registry
  path, synthetic test-only credentials, and a public SHA-256 test vector.
  Their source contexts were reviewed; no real credential was identified.
- Gitleaks is not installed. `detect-secrets` was used as the available
  equivalent. These scans do not cover ignored local files, databases, model
  weights, or arbitrary runtime data.
- An independent review and penetration test were not completed.

## Portable package runtime check

Artifact:
`TheraSim-v0.3.1-Windows-x64-Portable.zip` (portable one-folder ZIP, Windows
x64); SHA-256:
`df1be242f0040b67b9b15ad7e7d7f52e136ed260f690f79370716200d9715319`.
The 26,345,293-byte archive matched its `.sha256` sidecar and JSON manifest.

The fresh archive contained 1,110 entries under one top-level `TheraSim/`
directory and 19 allowed SQL migrations. Inspection found no database,
database sidecar, backup, `.env`, provider settings, API-key, model-weight, or
unsafe absolute/traversal archive path. The fresh extraction test on Windows
11 Pro x64 used system-only `PATH`, synthetic temporary data, and no existing
user database. It verified startup, UI delivery, local-account persistence
across restart/re-extraction, graceful shutdown, and one synthetic chat
through the already-installed local Ollama `qwen2.5:3b` model. No real patient
data was used. This is not a clean-device or network-disconnection test.

## Release-blocking considerations and user guidance

1. Do not enter real patient/client information. A user-configured remote
   provider may receive submitted text.
2. The operational and restricted SQLite databases are not encrypted at rest.
   Protect the Windows account and filesystem; keep backups in a protected
   location.
3. Do not commit `.env` files, API keys, provider settings, live databases,
   logs, backups, or model weights. Existing ignore rules cover these common
   artifacts, but review every proposed change before publication.
4. Do not publish a release ZIP until the fresh package has been built,
   extracted, inspected, smoke-tested, and checksummed. A workflow or a
   pre-existing archive alone is not evidence that the current source was
   packaged.
5. Verify the exact remote/branch and review staged changes before any commit
   or push. Never force-push or overwrite existing release history.

This audit records source-visible controls and bounded test results only.
Dependency checks and secret scans found no known dependency vulnerabilities
or reachable-history secrets, but Bandit reported the documented findings and
Gitleaks/independent review/penetration testing were unavailable. It does not
certify security, privacy compliance, clinical safety, or fitness for use
with real clinical data.
