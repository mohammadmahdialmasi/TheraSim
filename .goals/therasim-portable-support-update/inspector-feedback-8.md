# Inspector Feedback — Iteration 8

## Verdict: BLOCKED

## Acceptance Criteria Check

- [x] Provider-key documentation — VERIFIED: `ProviderSettingsStore` confirms that an explicitly entered UI key is protected with DPAPI on Windows, an omitted `api_key` preserves the last user-saved key, environment keys override saved values only in runtime settings, and an environment-only key is not newly persisted. `README.md`, `INSTALL_WINDOWS.md` (English and Persian), and `docs/RELEASE_AUDIT_v0.3.0.md` all state these distinctions consistently. Non-Windows persistent provider-key storage is explicitly described as unsupported.
- [x] Release-audit browser evidence — VERIFIED: the audit records `fa/rtl` and `en/ltr`, reload-persisted language preference, a 346px viewport with 331px document/main widths and no horizontal overflow, the complete sanitized support preview, loopback-only model probes, and synthetic-profile cleanup. It also correctly records the process as PID-terminated rather than graceful-shutdown-verified.
- [x] Security-claim boundary — VERIFIED: the audit and implementation documentation explicitly leave the independent security review blocked/unverified and do not claim clean security.
- [ ] Clean-machine, graceful-shutdown, and accessibility gates — BLOCKED/UNVERIFIED: no completed evidence is present for clean-device startup/usability, graceful process shutdown, or comprehensive accessibility.
- [ ] Independent security review — BLOCKED/UNVERIFIED: no independent security reviewer result is available. The requested security/authentication findings cannot be completed or treated as passing.

## Quality Gate

- Command: `python -m pytest -q tests/test_provider_settings_env.py` from `backend`
- Result: PASS
- Details: 3 focused provider-key tests passed, covering environment-only non-persistence, explicit protected UI persistence, and environment runtime precedence with preserved saved-key storage.
- Command: `git diff --check`
- Result: PASS
- Details: no whitespace errors reported.
- Command: full backend suite, frontend suite/build/audits, Windows clean-machine smoke test, graceful-shutdown test, accessibility review, and independent security review
- Result: NOT ALL VERIFIED
- Details: this inspection made no code or package changes. The substantive release gates named above remain external or unverified; passing the focused provider tests and checking documentation do not close them.

## Issues Found

1. The substantive documentation and provider behavior now agree: explicit UI keys are DPAPI-protected on Windows, omission preserves the last user-saved key, environment keys override runtime behavior, environment-only keys are not newly persisted, and non-Windows platforms lack persistent provider-key storage.
2. The release audit consistently distinguishes browser evidence from clean-machine, shutdown, and accessibility validation. It does not represent the browser check as a clean security review or a clean-device test.
3. The independent security reviewer remains unavailable. Clean-machine testing, graceful-shutdown verification, and accessibility review also remain unavailable or unverified.

## What Must Be Fixed

- Complete the independent security/authentication review when the reviewer is available; do not claim clean security or publish until it is complete.
- Complete and record clean-machine Windows startup/usability, graceful-shutdown, and comprehensive accessibility evidence.
- Re-run applicable release quality gates and recheck the official remote/upstream state before publication.
- Do not publish, tag, push, or alter unrelated worktree content.
