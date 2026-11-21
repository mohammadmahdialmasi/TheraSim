# Repository audit

**Audit date:** 2026-11-21
**Scope:** application source, tests, configuration, localization, packaging,
documentation, and release inputs. Local databases, caches, virtual
environments, generated packages, and ignored backups were not inspected or
modified. See the [v0.3.0 final integration audit](V0.3.0_FINAL_INTEGRATION_AUDIT.md)
for the exact release file inventory and validation evidence.

This is a source and workflow audit, not a penetration test, clinical
validation, psychometric validation, or clean-device certification.

## Architecture and status

The application is organized as a Python/FastAPI backend, a React/TypeScript
frontend, separate SQLite operational and restricted-case databases, and a
Windows PyInstaller one-folder package. The desktop runtime binds to loopback
and keeps user data outside the replaceable package directory. The system
diagram and component responsibilities are documented in
[Project architecture](PROJECT_ARCHITECTURE.md).

ACT is the only runnable modality. The app can start without a configured
model; model-backed patient simulation and evaluation require a provider.
Ollama, LM Studio, llama.cpp, and custom OpenAI-compatible endpoints share a
provider client. Patient and evaluator model IDs may be configured separately,
with fallback to a provider's general model. Updating provider settings
requires an application restart for already-constructed agents to use them.

## Findings and disposition

| Finding | Evidence and impact | Disposition |
|---|---|---|
| Old manual-update package filter rejected the new Windows portable ZIP name. | The UI could not expose a checksum-verified asset if a release used the new agreed filename. | Fixed by accepting the v0.3.0 portable name while retaining the legacy Windows ZIP pattern; focused backend tests cover both. |
| Shared localization fallback and language persistence tests were registered inside the feature-catalog loop. | The same tests ran repeatedly, obscuring the true suite size. | Fixed by registering the behavior tests once outside the loop. |
| An earlier Windows package included a migration backup. | The v0.2.0 public ZIP is immutable and is documented as containing the backup. | v0.3.0 build and verifier include only source `.sql` migrations and compare the archive against the exact allowlist. |
| Provider settings and diagnostics can identify remote infrastructure if not minimized. | Provider URL/key fields and case/transcript content are sensitive. | Responses redact credential values; remote endpoints require explicit confirmation; support diagnostics use a narrow allowlist and do not send themselves. |
| Saved provider keys and live data have different protection levels. | Windows keys use current-user DPAPI; SQLite files are ordinary local files. Non-Windows persistent key storage is unsupported. | Limits are documented; protect the OS account, use environment keys on non-Windows, and do not place real patient data in the app. |
| Hardware estimates cannot generalize beyond observed devices. | Inventory currently queries NVIDIA via `nvidia-smi`; Intel/AMD acceleration is not assessed. | Hardware checking is optional, makes no model selection, and labels compatibility as unverified. Results are scoped to exact model/provider/context. |
| ACT evaluator output can fail exact-reference validation. | Local synthetic benchmark results include rejected output even with constrained JSON Schema. | Strict app-side validation is retained; invalid output is rejected; no evaluator model is recommended. |
| Automatic update installation is absent. | The update endpoint reads official stable-release metadata only. | UI explicitly describes the check as manual; it does not download or modify application files. |
| Windows distribution is a one-folder ZIP, not a single-file EXE or installer. | PyInstaller uses `COLLECT`; dependencies and UI assets live in the packaged directory. | Build and installation docs use the actual package format and separate user-data location. |

No broken imports were observed in the full backend suite or TypeScript build.
No additional runtime dead module, duplicate live implementation, or
unnecessary dependency was confirmed by this pass. Existing root backups and
historical materials were not deleted merely because they appear redundant.
No broad directory relocation was justified: backend routes/core/services/
persistence and frontend feature modules are already grouped by responsibility.

## Quality and dependency verification

Observed in this checkout:

- Backend: 507 tests passed with Python 3.13.9.
- Frontend: 18 tests passed; ESLint passed; TypeScript and Vite production
  build passed.
- `pip-audit` against both the backend lock and Windows packaging
  requirements: no known vulnerabilities reported at scan time.
- Full `npm audit --audit-level=moderate`: zero vulnerabilities reported.
- Bandit 1.9.2 reported 11 findings (0 high, 6 medium, 5 low). These include
  constrained internal SQL construction, fixed official HTTPS update
  metadata, and bounded subprocess calls. They were reviewed and not
  suppressed; details and residual trust assumptions are in
  [Security audit](SECURITY_AUDIT.md).
- The fresh package passed isolated startup, UI delivery, synthetic account
  initialization, restart/re-extraction persistence, graceful shutdown, and
  one local Ollama synthetic chat. See the integration audit for size, digest,
  machine scope, and archive-content review.

All automated checks are limited evidence. They do not establish clinical or
psychometric validity, security certification, accessibility, or compatibility
on all hardware.

## Organization and publication review

- Source assets, research materials, scenarios, rubrics, migrations, tests,
  and release documentation were retained; no user database was cleaned up.
- `.venv`, `node_modules`, `dist`, generated builds, local data, logs, backups,
  and model-weight formats are ignored or excluded from the package.
- `.goals/` is now ignored. Previously tracked process artifacts are removed
  from the release source tree while their local copies are preserved. Older
  commits remain in the pre-existing Git history; history was not rewritten.
- Build paths are repository-relative. User data is stored separately from
  replaceable binaries. A clean-machine installation, physical network
  isolation, non-Windows credential-storage implementation, and other GPU
  vendors remain unverified.
- Release metadata is versioned to `0.3.1`; rubric/protocol schema versions
  remain independently versioned by design.

## Product and research limitations

Use synthetic, fictional data only. Remote model endpoints may receive text
after local-only controls are explicitly disabled and remote use confirmed.
The single local reviewer account is not a multi-user authorization system;
live SQLite data is not encrypted at rest. ACT rubrics, evaluator output,
analytics, and simulated responses have no established clinical,
psychometric, or therapeutic validity. See [Security boundaries](SECURITY_BOUNDARIES.md),
[Local AI model evaluation](LOCAL_AI_MODEL_EVALUATION.md), and the
[bilingual user guides](USER_GUIDE.md).
