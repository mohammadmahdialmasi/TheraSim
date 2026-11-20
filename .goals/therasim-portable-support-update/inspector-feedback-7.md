# Inspector Feedback — Iteration 7

## Verdict: FAIL

## Acceptance Criteria Check

- [x] Environment-only key omission — VERIFIED: the focused test starts with `CUSTOM_OPENAI_API_KEY`, omits `api_key` in the update, and confirms no protected or plaintext key is written.
- [x] Explicit UI key protection — VERIFIED: the focused test enters an explicit key and confirms it is persisted as `api_key_protected`, without plaintext in the settings file.
- [x] Environment runtime precedence — VERIFIED: the focused test confirms a saved key can be preserved while the environment key remains the runtime key after save.
- [ ] Documentation of saved-key preservation and environment override — FAILED: the implementation preserves the last protected user-saved key when a settings update omits `api_key`, while environment values override it only at runtime. `README.md`, `INSTALL_WINDOWS.md`, and the release audit mention environment precedence and non-persistence, but do not accurately explain that a previously saved UI key is preserved; the English/Persian text also makes a Windows-capable saved-key implementation sound like all environment values are never written.
- [x] Release-audit browser evidence alignment — VERIFIED: `docs/RELEASE_AUDIT_v0.3.0.md` records `fa/rtl`, `en/ltr`, language persistence after reload, a 346px viewport with 331px document/main scroll widths, the full `diagnostics.json` preview, and loopback-only model probes. It consistently leaves clean-machine operation, graceful shutdown, and accessibility unverified.
- [ ] Security/authentication criterion — BLOCKED/UNVERIFIED: no dedicated security reviewer result is available or treated as passing. The audit and goal remain blocked, with no clean-security claim and no release publication.

## Quality Gate

- Command: `python -m pytest -q tests/test_provider_settings_env.py` from `backend`
- Result: PASS
- Details: 3 provider-key tests passed.
- Command: `python -m pytest -q` from `backend` with isolated `THERASIM_DATA_DIR`
- Result: PASS
- Details: 494 tests passed.
- Command: `npm test` from `frontend`
- Result: PASS
- Details: 34 frontend tests passed.
- Command: `npm run lint` from `frontend`
- Result: PASS
- Details: ESLint completed with no findings.
- Command: isolated `npm run build -- --outDir <temporary-directory> --emptyOutDir` from `frontend`
- Result: PASS
- Details: TypeScript and Vite build completed successfully outside the worktree.
- Command: `git diff --check`
- Result: PASS
- Details: no whitespace errors.

## Issues Found

1. The provider implementation correctly separates saved keys from runtime environment overrides, but the documentation is incomplete. It needs to state that an update which omits `api_key` preserves the existing user-saved key on Windows, that an environment key takes precedence only for runtime use, and that environment-only keys are not added to the provider-settings file.
2. The same preservation distinction should be consistent in English and Persian README/install text and in the release audit. The current broad “environment values ... are not written” wording may be read as covering cases where a previous saved key remains in the file.
3. The dedicated security/authentication review remains unavailable. Clean-machine, graceful-shutdown, and accessibility checks are also not verified; they must not be represented as passing.

## What Must Be Fixed

- Update README and INSTALL_WINDOWS English/Persian provider-key wording to distinguish:
  - explicit UI key entry creates protected saved storage;
  - an omitted key preserves the previous protected saved key;
  - environment keys override saved keys at runtime;
  - environment-only values are not newly written to provider settings.
- Reconcile the release audit's credential paragraph with the same preservation/override behavior.
- Keep security/authentication BLOCKED/UNVERIFIED and keep this release unpublished until the required review and remaining release gates are complete.
