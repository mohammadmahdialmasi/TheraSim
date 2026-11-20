# Inspector Feedback — Iteration 7

## Verdict: BLOCKED

## Acceptance Criteria Check

- [x] Environment-sourced provider-key persistence finding — verified in the worktree: `ProviderSettingsStore` retains the last persisted key separately from runtime settings and does not persist an environment-only key when the UI omits it. Explicitly entered UI keys are still protected before persistence. Focused tests cover both behaviors and preserving environment precedence.
- [x] Release-audit wording finding — verified: `docs/RELEASE_AUDIT_v0.3.0.md` now records the packaged-browser evidence for `fa/rtl`, `en/ltr`, language persistence, narrow layout, and diagnostics preview in the package summary and detailed section. The remaining caveats are consistent: clean-machine operation, graceful shutdown, and accessibility remain unverified.
- [ ] Release readiness — BLOCKED, not represented as a clean security result. The audit explicitly says the independent security review is blocked/unverified and not passed or clean. No security reviewer was rerun. No release, tag, or remote publication was attempted.

## Quality Gate

- Command: `python -m pytest -q tests/test_provider_settings_env.py tests/test_provider_config.py` from `backend`
- Result: PASS
- Details: 28 tests passed. One pytest deprecation warning was emitted by the installed `anyio` plugin.
- Command: `git diff --check`
- Result: PASS
- Details: No whitespace errors; Git emitted only line-ending conversion warnings.

## Issues Found

The two requested worktree fixes passed the focused verification. However, the provider settings module required for the fix (`backend/app/core/provider_settings.py`) is untracked and the implementation depends on it. It cannot safely be included in this Inspector commit: that would commit an entire pre-existing product module, while omitting it from a product commit would leave the fix unusable. Accordingly, the product fix remains uncommitted and this iteration is BLOCKED. The worktree also contains other modified and untracked product files; none were staged or committed by this inspection.

The independent security/authentication review, clean-machine package check, graceful-shutdown check, and full accessibility review remain blocked or unverified. This inspection does not claim clean security or release clearance.

## What Must Be Fixed

- Preserve the provider settings module and its dependent fix in the appropriate product change/commit workflow; do not include unrelated pre-existing product work.
- Complete the independent security review and the remaining release checks before considering publication. Keep the release unpublished until then.
