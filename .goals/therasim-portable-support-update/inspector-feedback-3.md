# Inspector Feedback — Iteration 3

## Verdict: FAIL

## Acceptance Criteria Check

- [ ] Criterion 1 — PARTIALLY verified: `docs/RELEASE_AUDIT_v0.3.0.md` distinguishes implementation boundaries and explicitly records the security review as blocked/unverified. This is not a completed authentication/security audit; none was performed in this review.
- [ ] Criterion 2 — PARTIALLY verified: `npm test` passes the English/Persian unique-key and feature-catalog parity tests, and the backend has language-specific archive README content. The Persian README mirrors the main setup guidance, but the detailed Windows support/setup instructions added to `INSTALL_WINDOWS.md` are English-only. No browser RTL/LTR or screen-reader check was run.
- [ ] Criterion 3 — FAILED: backend preview/export and Persian archive behavior pass focused tests, including explicit confirmation, a two-file allowlisted ZIP, and language-specific README/filename. The UI fetches `/support/preview`, but renders only translated static category summaries plus the live application version and language; it does not display the full report fields returned by the endpoint. The English UI says it previews “the exact diagnostic fields,” which overstates what is shown. Frontend tests assert source patterns, not rendered UI or an end-to-end download.
- [ ] Criterion 4 — BLOCKED/UNVERIFIED: provider security behavior was not independently audited. The explicitly required security review remains unavailable and unperformed; no clean security/authentication finding is claimed.
- [ ] Criterion 5 — BLOCKED/UNVERIFIED: a full authentication/credential-storage, migration, cleanup, and update safety review was not performed in this iteration.
- [ ] Criterion 6 — NOT VERIFIED: the docs describe manual/read-only update checks and explicitly say automatic installation is unsupported; the update implementation was not independently revalidated in this iteration.
- [ ] Criterion 7 — PARTIALLY verified: the existing v0.3.0 ZIP sidecar SHA-256 matches the archive. `verify-windows-package.ps1` extracted it into a fresh temporary directory and passed startup, health/API, UI response, synthetic-account initialization, and isolated persistence checks. The ZIP’s bundled frontend JavaScript is byte-identical to a fresh build of the current frontend. The package check did not exercise the Persian UI/support workflow or verify graceful shutdown; no clean-machine test was run.
- [ ] Criterion 8 — PARTIALLY verified: focused backend support tests passed (4); all frontend tests passed (31), lint passed, and an isolated frontend production build passed. The full backend suite, dependency audits, and a fresh Windows package build were not run in this iteration.
- [x] Criterion 9 — Verified for the inspected commits: `0af02ec` contains six support/test/package-script files and `c96be0a` contains the two Windows/README documentation files; these are task-related. The index is currently empty and no remote action was taken. Numerous pre-existing unstaged/untracked changes remain; notably, the current `App.tsx` support UI changes are unstaged and are not part of either inspected commit. They were preserved.

## Quality Gate

- Command: `python -m pytest -q tests/test_support_export.py` from `backend` (isolated temporary data path)
- Result: PASS
- Details: 4 passed; one third-party pytest-plugin deprecation warning.

- Command: `npm test` from `frontend`
- Result: PASS
- Details: 31 passed, including English/Persian catalog parity and focused support-source assertions.

- Command: `npm run lint` from `frontend`
- Result: PASS

- Command: `npm run build -- --outDir <temporary-directory> --emptyOutDir` from `frontend`
- Result: PASS
- Details: production build succeeded without changing the existing `dist/frontend` output.

- Command: `./scripts/verify-windows-package.ps1 -PackageZip ./dist/TheraSim-v0.3.0-windows-x64.zip -Port 18769`
- Result: PASS
- Details: temporary extraction and synthetic local persistence smoke test passed. The archive SHA-256 matched its sidecar, and its embedded frontend bundle matched a fresh build byte-for-byte.

- Command: full backend suite, `pip_audit`, `npm audit`, fresh Windows package build, browser localization/UI checks, and independent security review
- Result: NOT RUN
- Details: these broader checks were outside this focused verification; the security review remains specifically unavailable and unperformed.

## Issues Found

1. The support screen fetches the server preview but only displays its application version and language alongside fixed included/excluded category copy. It does not show the actual allowlisted runtime, service, provider, or connection-status values from the preview response, despite the English “exact diagnostic fields” claim. The focused frontend tests only inspect source text and do not catch this UI limitation.
2. The detailed Windows support/setup guide is in English. The Persian README has a matching high-level setup summary, but does not provide equivalent detail for the support-export flow and troubleshooting covered in the guide.
3. Package and core support checks provide useful evidence, but do not close the full release gate: no clean-machine test, bilingual browser workflow, graceful-shutdown assertion, full backend/dependency gates, or independent authentication/security review was completed.
4. The inspected builder commits are narrowly scoped, but the current `App.tsx` support UI flow is still unstaged. No unrelated or pre-existing worktree content was staged or committed by this review.

## What Must Be Fixed

- Render the actual sanitized preview fields before confirmation (or change the UI wording so it accurately describes a summary), and add behavior-level tests for English/Persian preview and the resulting download filename.
- Provide equivalent Persian detail for the Windows support/setup/troubleshooting instructions, or otherwise make the bilingual documentation boundary explicit.
- Keep the security/authentication review marked blocked/unverified until it is actually performed. Run the remaining full release gates and representative browser/package checks before treating the release as verified.
