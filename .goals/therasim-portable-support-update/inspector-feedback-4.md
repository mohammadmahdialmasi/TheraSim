# Inspector Feedback — Iteration 4

## Verdict: FAIL

## Acceptance Criteria Check

- [ ] Criterion 1 — BLOCKED/UNVERIFIED: `docs/RELEASE_AUDIT_v0.3.0.md` explicitly records that the requested security review did not return analysis because no model endpoint was available. I did not perform an authentication/security audit in this iteration, and I make no security findings or claim of a clean review.
- [ ] Criterion 2 — FAILED: English/Persian translation parity tests pass, and the Windows guide contains substantial Persian counterparts. However, the Persian guide omits the English guide's default port `8765`, supported `THERASIM_PORT` range `1024`–`65535`, and warning not to use the published v0.2.0 package. Both language sections also still describe the support page as showing only a summary, while the current UI displays the entire sanitized response. No browser RTL/LTR or narrow-layout check was performed.
- [x] Criterion 3 — VERIFIED from source and focused tests: `SupportExport` requests `/api/v1/support/preview` with the selected language, rejects a preview whose response language differs, and renders `formatSupportPreview(...)` in a `<pre>`. That formatter serializes the entire response object via `JSON.stringify(preview, null, 2)`. The UI requires preview availability and explicit confirmation before export. The selected language is passed to the export request; the returned `Content-Disposition` filename is used for the browser download, with English and Persian fallbacks. Frontend tests cover complete JSON serialization and both language-specific download names; backend tests cover the Persian preview/export and archive README.
- [ ] Criterion 4 — BLOCKED/UNVERIFIED: the requested provider/authentication security review was not performed because the previously invoked security-review task failed before analysis for lack of a model endpoint. No security findings are made.
- [ ] Criterion 5 — BLOCKED/UNVERIFIED: the broader authentication/credential, migration, cleanup, and update safety audit was not independently completed in this iteration. Treat related release acceptance as blocked, not passed.
- [ ] Criterion 6 — UNVERIFIED: I did not independently verify update detection and source-checkout workflow behavior in this focused review. The criterion remains part of the uncompleted release gate.
- [ ] Criterion 7 — FAILED for the current source state: the existing `dist/TheraSim-v0.3.0-windows-x64.zip` has a valid matching SHA-256 sidecar and passes the repository's fresh-extraction smoke script. The extracted app serves health/UI endpoints and creates a synthetic account/database under a temporary profile. However, the ZIP embeds `TheraSim\_internal\frontend\assets\index-C8jwXNMD.js`, while a fresh isolated build from the current frontend produces `index-DVMkd1MA.js`; the packaged bundle also lacks the current “Exact sanitized preview” text. Thus the available ZIP is not verified as a package of the current source. The smoke script checks database creation, not account persistence across a process restart. Clean-machine, localized-browser, and graceful-shutdown checks remain unverified.
- [ ] Criterion 8 — PARTIALLY VERIFIED; release gate remains BLOCKED: frontend tests, lint, isolated production build, and the focused backend support-export tests pass. The full backend suite, dependency audits, a fresh Windows package build, and the outstanding security/auth review were not run in this iteration.
- [x] Criterion 9 — VERIFIED for this inspection's repository actions: the index was empty before the inspector changes, and no push, fetch, tag, release, or other remote mutation was performed. `git status -sb` showed local branch `release-fix` ahead of `origin/main` by 5 commits. Numerous pre-existing staged/unstaged/untracked worktree items were present; they were not staged or changed by the verification commands. This inspection commit must include only this feedback file and `status.json`.

## Quality Gate

- Command: `npm test` from `frontend`
- Result: PASS
- Details: 34 tests passed, including English/Persian translation-key parity, complete support-preview serialization for both languages, language-mismatch rejection, and language-specific download filename handling.

- Command: `npm run lint` from `frontend`
- Result: PASS
- Details: ESLint completed without findings.

- Command: `npm run build -- --outDir <temporary-directory> --emptyOutDir` from `frontend`
- Result: PASS
- Details: TypeScript and Vite production build succeeded in an isolated temporary directory; the existing `dist/frontend` output was not targeted.

- Command: `python -m pytest -q tests/test_support_export.py` from `backend`, with temporary `THERASIM_DATA_DIR`
- Result: PASS
- Details: 4 tests passed; one third-party pytest-plugin deprecation warning.

- Command: verify sidecar and inspect `dist/TheraSim-v0.3.0-windows-x64.zip`
- Result: PASS for archive integrity only
- Details: SHA-256 expected and actual were both `18a478057852a0041073d41144963d4169f55d9237b7817035cba0760335299d`; the ZIP has 489 entries and no `.bak` entries. This checksum does not establish that the package matches current source.

- Command: `scripts/verify-windows-package.ps1 -PackageZip ./dist/TheraSim-v0.3.0-windows-x64.zip -Port 18769`
- Result: PASS for the existing ZIP's limited smoke checks
- Details: package migration SQL entries matched the source allowlist, fresh extraction succeeded, the app reached health and UI endpoints, synthetic account initialization succeeded, and an isolated local database file was created. It did not validate persistence across restart, current-source bundle parity, localized UI behavior, clean-device operation, or graceful shutdown.

- Command: independent security/authentication review and dependent release checks
- Result: BLOCKED/UNVERIFIED
- Details: the prior security-review task failed before analysis because no model endpoint was available. No security findings or clean-review conclusion are claimed. Broader security/authentication and dependent release acceptance criteria remain blocked.

## Issues Found

1. The Windows ZIP is stale relative to the current frontend source: the packaged asset hash differs from a fresh build, and the package does not contain the new support-preview label. A passing checksum only verifies the ZIP against its own sidecar.
2. The English and Persian Windows guide sections are not fully at parity: the Persian section omits the default port and valid port range, as well as the v0.2.0 package warning. Both sections inaccurately say the support page shows a summary, although the current UI renders the full sanitized report.
3. Package persistence evidence is limited to account initialization and database-file creation. Persistence through a restart was not verified. Browser RTL/LTR behavior, clean-machine startup, and graceful shutdown also remain unverified.
4. The independent security/authentication review remains blocked. No security findings are made, and release acceptance depending on that review remains blocked/unverified.
5. The worktree contains extensive pre-existing changes. The index was empty at inspection start; only the two process-artifact files may be staged for this inspector commit.

## What Must Be Fixed

- Rebuild the Windows x64 candidate from the current source into a new output path, verify its SHA-256, inspect its contents, and rerun fresh-extraction startup/API/UI and persistence checks. Do not overwrite or replace the existing candidate as part of this inspection.
- Bring the Persian Windows guide into parity with the English warning and port details, and update both language sections to accurately describe the full sanitized preview displayed by the current UI.
- When a security-review model endpoint is available, complete the requested independent security/authentication review. Until then, keep security/auth and dependent release criteria marked BLOCKED/UNVERIFIED; do not publish or represent the release as verified.
- Complete the remaining release gates, including the full backend suite, relevant dependency checks, and representative browser/localization and package checks, before treating the release as verified.
