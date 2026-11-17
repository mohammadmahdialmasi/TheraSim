# Inspector Feedback — Iteration 1

## Verdict: FAIL

## Acceptance Criteria Check

- [x] Criterion 1 — PARTIALLY verified: source audit/release documentation exists in `docs/RELEASE_AUDIT_v0.3.0.md` and `docs/RELEASE_CHECKLIST.md`, with implementation boundaries and release status. This remains incomplete as a release-clearance audit because independent source verification, the actual package, and the blocked security review are not complete.
- [ ] Criterion 2 — FAILED: English/Persian support copy exists, but `frontend/src/i18n.ts` contains duplicate `providerError` keys in both catalogs, TypeScript build reports `TS1117` at lines 156 and 378, frontend test reports 218 versus 219 English/Persian keys, and `npm run build` fails. RTL/LTR document direction and catalog behavior are present, but complete localization verification cannot pass until the catalogs build.
- [ ] Criterion 3 — FAILED: the backend has strict confirmation and a two-file allowlisted archive, and `backend/tests/test_support_export.py` passes leak-prevention checks. However, the frontend's preview is static catalog copy rather than a result from `/api/v1/support/preview`, and `downloadSupportArchive()` always sends `{ confirmed: true }` without `language`, while the browser download always chooses `TheraSim-support-diagnostics.zip`. Thus Persian UI export is not consistently language-aware and English/Persian filenames/content cannot be asserted end to end.
- [ ] Criterion 4 — BLOCKED/UNVERIFIED: provider settings and endpoint protections exist and backend/provider tests pass as part of the 490-test backend suite, but the explicitly required security review did not run because no model endpoint was available. It must not be treated as passing or evidence of no vulnerabilities.
- [ ] Criterion 5 — PARTIALLY verified: source and migration/update documentation and backup/migration tests exist in the backend suite, and no destructive source update was performed during inspection. A full independent authentication/credential, migration, cleanup, and update assessment cannot be passed because the security-review requirement is blocked.
- [ ] Criterion 6 — PARTIALLY verified: update code/docs state manual/read-only behavior and explicitly say automatic installation is unsupported. Portable source/package safety documentation is present, but package verification was not possible and the localization/build blocker prevents a valid release package.
- [ ] Criterion 7 — FAILED/UNVERIFIED: no actual `dist/TheraSim-v0.3.0-windows-x64.zip` candidate existed. The environment has Python 3.13 x64, but frontend build fails and the package workflow has not produced or smoke-tested the actual ZIP. Clean-machine startup, UI/API, persistence, localization, and shutdown are unverified.
- [ ] Criterion 8 — FAILED: backend suite passed (490 tests), npm lint passed, pip-audit found no known vulnerabilities, npm audit found 0 vulnerabilities, but frontend tests have 1 failure and frontend build fails with duplicate `providerError` keys. The Windows package gate is not runnable successfully until that blocker is fixed. This is a genuine release blocker.
- [ ] Criterion 9 — FAILED: the repository is on an ahead-of-origin branch with unrelated/uncommitted work preserved; no push, tag, release, or publication was performed. No release artifact is verified, and the official remote/upstream and release publication gates have not been cleared.

## Quality Gate

- Command: `python -m pytest -q` from `backend`, with isolated `THERASIM_DATA_DIR`
- Result: PASS
- Details: 490 tests passed, 1 third-party pytest-plugin warning.

- Command: `npm run lint` from `frontend`
- Result: PASS
- Details: ESLint completed without findings.

- Command: `npm test` from `frontend`
- Result: FAIL
- Details: 28 of 29 Node tests passed. The localization catalog parity test failed: 218 English keys versus 219 Persian keys.

- Command: `npm run build` from `frontend`
- Result: FAIL
- Details: TypeScript reports duplicate object properties at `frontend/src/i18n.ts:156` and `:378`; both duplicate key is `providerError`.

- Command: `python -m pip_audit -r backend/requirements-lock.txt`
- Result: PASS
- Details: No known vulnerabilities found by pip-audit.

- Command: `npm audit --omit=dev --audit-level=moderate`
- Result: PASS
- Details: npm reported 0 vulnerabilities.

- Command: repository Windows package build and verification scripts
- Result: BLOCKED
- Details: No pre-existing package candidate was found. The frontend build failure prevents construction of a verified package, and no clean-device smoke test or SHA-256 verification was performed.

- Command: explicitly invoked security review
- Result: BLOCKED/UNVERIFIED
- Details: The security-review agent failed before analysis because no model endpoint was available. No security findings are claimed or inferred.

## Issues Found

1. Duplicate `providerError` entries exist in both central language catalogs. This breaks TypeScript compilation and localization parity.
2. `frontend/src/lib/api.ts` exports support archives without forwarding the selected UI language and `frontend/src/App.tsx` assigns a fixed English download filename. The backend supports English/Persian filename and README content, but the browser workflow does not pass or display that language consistently.
3. The support frontend does not call `GET /api/v1/support/preview`; it shows static catalog copy. The backend preview endpoint returns the allowlisted report, so the UI preview is not proven to be generated from the exact export fields.
4. The actual v0.3.0 Windows ZIP, checksum, extraction, startup/UI/API/persistence/localization/shutdown smoke test, and clean-device validation are absent.
5. The independent security review remains unavailable and must stay recorded as blocked/unverified.

## What Must Be Fixed

- Remove duplicate `providerError` entries and make the English/Persian central catalogs structurally identical; rerun lint, tests, build, and localization/browser checks.
- Make the support export flow use the selected language and return/server filename consistently. Add or extend tests for Persian preview/export and browser filename behavior, and ideally fetch the backend preview before showing confirmation so the preview is the exact export allowlist.
- Rebuild the frontend successfully, then produce and verify the actual Windows package using isolated temporary data. Record SHA-256 and extraction/smoke-test evidence or leave clean-device/package status unverified.
- Re-run the security review when a model endpoint is available. Do not represent the present state as security-clean.
- Before any publication, preserve existing worktree changes, confirm intended files and upstream/remotes, and clear all remaining release gates.
