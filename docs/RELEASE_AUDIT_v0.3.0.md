# TheraSim v0.3.0 — Source and Release Audit

**Audit date:** 2026-11-17
**Release status:** Not published; verification required

This report distinguishes source-verified implementation evidence from findings
that still require an external or clean-device check. It does not represent a
clinical, psychometric, or independent security validation.

## Product and source verification

| Area | Source-verifiable result | Boundary |
|---|---|---|
| Runtime | FastAPI serves the bundled React application on loopback in the Windows desktop runtime. | Start, health, UI, and isolated persistence are operationally smoke-tested where Windows automation is available. |
| Data | Operational and restricted SQLite databases use independent migration histories and paired backup/restore tooling. | Live SQLite files are not encrypted at rest. A restore destination must be separate from an active or existing user directory. |
| Authentication | A single local reviewer account, bearer sessions, and persistent login throttling are implemented. | This is not multi-user authorization or password recovery. |
| Provider configuration | Provider settings and connection diagnostics are implemented with redacted settings responses and explicitly configurable endpoints. | A remote HTTPS or HTTP endpoint requires explicit trust and must not receive real-person data. |
| Support diagnostics | A strict export implementation and leak-prevention tests are required before publication. | The dedicated credential/support security review has not been recorded as complete in this audit. |
| Updates | Update checks are manual/read-only and report stable release metadata without applying files or invoking Git. | Automatic download and installation are not implemented; source checkout status is read-only. |
| Windows package | A one-folder x64 PyInstaller ZIP workflow is implemented and migration `.sql` resources are allow-listed. | Clean-device startup, persistence, shutdown, and localization remain unverified unless the Windows smoke test is run in a representative environment. |
| Clinical scope | ACT is the only runnable modality; analytics and evaluator output are experimental. | No clinical efficacy, evaluator reliability, psychometric validity, or therapeutic outcome is claimed or established. |

## Authentication and credential review

The repository separates live SQLite data, bearer-session metadata, provider
configuration, and optional backups. Provider API keys must be treated as
secrets: do not place them in public issues, support logs, screenshots, or
source control. Plain live provider settings and live databases remain
protected only by the host operating system and account permissions. Export
and provider behavior should be judged by the focused security review before
release publication.

**Security review blocker:** the requested read-only security review did not
return any analysis because no model endpoint was available. Its status is
blocked/unverified, not passed or clean. Credential handling, provider URL
enforcement, connection diagnostics, support export, and directly related tests
must remain unchanged until a review can run with an available endpoint.

## Migration and cleanup

Paired backup and restore tests cover:

- verified database copies and SHA-256 manifests;
- encrypted round trips and wrong-passphrase rejection;
- ciphertext tampering;
- destination collision protection;
- WAL-mode refusal;
- database-lock failure guidance;
- restore into a new directory only.

Migration and backup operations are not destructive source updates. The
application does not automatically delete, rotate, or purge backup sets. Stop
TheraSim before backup or restore operations that require a point-in-time pair.

## Update safety

The implemented update check:

- runs only when requested;
- accepts stable GitHub release metadata only;
- validates official release URLs and SHA-256 asset digests;
- reports source-checkout state without exposing changed paths;
- never runs `git pull`, `git reset`, `git checkout`, or an installer.

Automatic application installation remains explicitly unsupported. Users must
download and verify a package themselves. The portable ZIP is not evidence of
an upgrade mechanism and must not replace the existing application folder
while the application is running.

## Localization and documentation

English and Persian catalogs describe the same implemented behavior and
limitations. RTL/LTR behavior and mixed-direction identifiers require browser
review; automated parity checks do not replace a narrow-layout and
screen-reader inspection. Beginner setup, data, backup, troubleshooting,
credential, remote-provider, and package-limit guidance must remain consistent
in both languages.

## Package verification status

The Windows workflow must produce `TheraSim-v0.3.0-windows-x64.zip`, verify
its migration resources against the source `.sql` allowlist, run the isolated
temporary-profile smoke test, and calculate an SHA-256 checksum. A locally
built candidate is not a public release asset. A clean-machine test is
**unverified** unless performed with recorded Windows/runtime versions.

## Publication gate

No commit in this repository alone authorizes publication. Before any tag or
GitHub Release:

1. complete all focused security findings and release checks;
2. run backend, frontend, dependency, localization, backup, migration, and
   Windows package gates;
3. verify the exact workflow-generated ZIP and sidecar checksum;
4. confirm no existing database, credential, `.env`, log, backup, or
   unrelated worktree file was included;
5. confirm the official remote and upstream state are non-conflicting;
6. obtain the maintainer's explicit authorization to push, tag, or publish.
