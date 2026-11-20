# Inspector Feedback — Iteration 6

## Verdict: FAIL

## Acceptance Criteria Check

- [ ] Criterion 1 — PARTIALLY VERIFIED / BLOCKED: `docs/SECURITY_AUTHENTICATION_AUDIT.md` is clearly labeled “Inspected design only; independent security review blocked/unverified.” It explicitly rejects a clean-security claim and says the source checks do not substitute for the unavailable review. The requested independent security/authentication review is not complete; no security findings or clean-review conclusion are made here.
- [ ] Criterion 2 — PARTIALLY VERIFIED: README and both English and Persian Windows installation sections now describe Windows DPAPI storage as current-user scoped, distinguish the protected blob from plaintext, describe legacy-key migration, and state that persistent provider-key storage is unavailable off Windows. The parent-reported packaged-browser evidence verifies `fa/rtl` and `en/ltr`, language persistence after reload, a 346px viewport with document/main widths of 331px and no horizontal overflow, and the full support JSON preview. However, the bilingual wording that environment values “are not written” to the provider settings file is too broad relative to the source save path (see Issues Found). Accessibility remains unverified.
- [x] Criterion 3 — VERIFIED from prior iteration evidence and the current reported browser check: prior iteration-5 tests verified allowlisted support export and language-aware archive behavior; current reported browser evidence confirms the complete sanitized support JSON preview rendered from the fresh package. Export still requires confirmation. This does not close the independent security-review blocker.
- [ ] Criterion 4 — BLOCKED/UNVERIFIED: the dedicated independent security review remains unavailable. No security findings are made and no clean review is claimed.
- [ ] Criterion 5 — PARTIALLY VERIFIED / BLOCKED: provider credential-storage wording was compared with `credential_store.py`, `provider_settings.py`, and the settings update path. Windows DPAPI and environment precedence are described substantially accurately, but the statement that environment values are not written to the settings file does not describe the Windows UI-save path in all cases. The broader independent authentication/credential and data-safety review remains blocked.
- [x] Criterion 6 — VERIFIED from the current release audit wording and prior iteration-5 source/tests: update checks are described as manual/read-only and automatic installation as unsupported. No new update behavior was independently exercised in this iteration.
- [ ] Criterion 7 — PARTIALLY VERIFIED: parent-reported evidence is from a fresh package extraction and covers synthetic-account use, English/Persian direction and language persistence, narrow layout, and complete support preview. It does not verify graceful shutdown or clean-machine operation. Those remain blockers/unverified.
- [ ] Criterion 8 — PARTIALLY VERIFIED / BLOCKED: `git diff --check` passed. The previous iteration-5 feedback records passing backend (491 tests), frontend (34 tests, lint, isolated build), dependency audits, package verification, and restart persistence. Those suites were not rerun for this inspection; the independent security review and the remaining package checks still prevent release clearance.
- [x] Criterion 9 — VERIFIED for repository actions in this inspection: no product commit, push, tag, or release publication was made. The latest commit before this inspector commit was the iteration-5 inspector commit. The index was empty; numerous existing modified and untracked product/worktree files remain unstaged and were preserved. Local tags include v0.2.0 and v0.2.1, not v0.3.0. Parent-reported read-only remote inspection found the official origin URL, `main` still at `82298889912206ac8c07e834e463dd0fba26a263`, and no v0.3.0 tag; no remote writes occurred.

## Quality Gate

- Command: `git diff --check`
- Result: PASS
- Details: no whitespace errors were reported.

- Commands: backend pytest, frontend tests/lint/build, dependency audits, and Windows package build/verification
- Result: NOT RERUN in this inspection
- Details: iteration-5 feedback records these checks as passing (491 backend tests; 34 frontend tests; frontend lint/build; pip-audit and npm audit; isolated package smoke and restart-persistence checks). The current iteration's parent-reported browser evidence supplements, but does not replace, those gates or clean-machine/graceful-shutdown validation.

- Independent security/authentication review
- Result: BLOCKED/UNVERIFIED
- Details: reviewer unavailable. No security findings and no clean-security claim are made.

## Issues Found

1. **Environment-key persistence wording is overbroad in both languages.** The README and English/Persian Windows setup text say environment values take precedence and are not written to the provider settings file. Source inspection shows `ProviderSettingsStore.load()` applies provider environment values to the runtime `Settings`; on a later Windows settings save, `ProviderSettingsStore.update()` uses the current runtime key when an incoming `api_key` is omitted, then writes a protected `api_key_protected` value. The frontend normally omits an empty key field, so this path can persist the environment-sourced key in protected form. This is a documentation/source behavior mismatch, not a security finding. Either make the implementation guarantee environment-sourced values are never saved, or narrow the English and Persian wording to accurately describe the behavior.
2. **The release audit has stale/ambiguous verification statements.** `docs/RELEASE_AUDIT_v0.3.0.md` still says RTL/LTR behavior “require[s] browser review” and its package table says localization remains unverified, while a later section in the same document records the completed packaged-app browser check, including `fa/rtl`, `en/ltr`, reload persistence, narrow viewport, and the full diagnostics preview. Reconcile those statements. Keep clean-machine validation, graceful shutdown, and comprehensive accessibility marked unverified.
3. **Release blockers remain:** the independent security review, clean-machine validation, graceful shutdown, full accessibility review, and release publication gate have not been completed. Keep v0.3.0 unpublished and do not describe the security review as clean.
4. The worktree contains many unrelated/pre-existing modified and untracked files. They were not changed or staged by this inspection; only the feedback and status files may be included in this inspector commit.

## What Must Be Fixed

- Correct the environment-key persistence wording in the README and both English/Persian installation sections, or change the implementation so the documented non-persistence is guaranteed; add a focused test for the chosen behavior.
- Reconcile the release audit’s browser/localization statements with its recorded packaged-browser evidence without overstating accessibility, clean-machine, or shutdown verification.
- Keep independent security review explicitly BLOCKED/UNVERIFIED and complete it when a reviewer is available. Until then, do not claim clean security or publish the release.
- Complete clean-machine, graceful-shutdown, and full accessibility checks before release publication. Preserve unrelated worktree changes and make no product commit or remote publication as part of this inspector iteration.
