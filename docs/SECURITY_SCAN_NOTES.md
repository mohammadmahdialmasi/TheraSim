# Security scan notes

## v0.3.0 verification

- `pip-audit` against the locked backend and Windows packaging dependencies
  reported no known vulnerabilities at scan time.
- Full `npm audit --audit-level=moderate` reported zero vulnerabilities.
- Bandit 1.9.2 reported 11 findings (0 high, 6 medium, 5 low). SQL-fragment
  warnings were reviewed as constrained internal SQL, the URL finding is the
  fixed official HTTPS update endpoint, and subprocess warnings are bounded
  calls without a shell. They remain visible; no blanket suppression was
  added. See [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md).
- `detect-secrets` 1.5.0 scanned the intended publication file list with
  network verification disabled. Nine candidates were reviewed: a Windows
  registry path, synthetic test-only credentials, and a public SHA-256 test
  vector. No real credential was identified.
- `.goals/` process files were excluded from the v0.3.0 source tree and
  preserved locally. Earlier tracked copies remain in existing Git history;
  no history rewrite or force push was performed.

These are bounded source and dependency checks, not a penetration test or
independent security review. Gitleaks was unavailable.

## v0.2.1 historical secret scan

Gitleaks v8.30.1 scanned all local Git refs and history with full redaction
(`--redact=100`). Its JSON report was written under the operating-system
temporary directory and was not committed.

The history scan reported four `generic-api-key` matches: lines 543 and 550 of
`backend/tests/test_evaluation_service.py` in commits
`3d2190e102af307384144d753661014e27041661` and
`0f7e226a91aaf08009554e2265f98c5510061341`. These are two repeated test-fixture
identifier arguments (`run_id`, `session_id`, and message IDs) passed to
`seed_completed_evaluation_session`, not provider credentials or access tokens.
The source context was reviewed with literal values redacted; the full-redaction
Gitleaks report exposed no secret values. The findings are retained in history
and were not rewritten or hidden.

The staged v0.2.1 product changes scan found zero findings with full redaction.
Both scan reports remain in TEMP and were not committed.

## v0.2.1 historical dependency audits

- `pip-audit` found no known vulnerabilities in the backend or Windows build
  requirements.
- `npm audit --omit=dev --audit-level=moderate` found no production dependency
  vulnerabilities.
- The full frontend `npm audit` reports 11 high-severity findings associated
  with the unpatched `picomatch` advisory GHSA-fc5q-39xc-vjpf in the development
  toolchain. The advisory lists no patched version; a forced fix would require
  a breaking dependency downgrade. No forced downgrade was applied. The
  production-only audit remains the package release gate.

## v0.2.1 historical data handling

Backend tests and the Windows package smoke test used fresh temporary data
directories. No default local SQLite database was opened, queried, seeded,
hashed, or used for release evidence.

## v0.2.1 historical local package smoke test

The local v0.2.1 release-candidate archive built for verification had SHA-256
`fb8a95ea01ec13a0d5c5219d75c4b7cb889b3e81a86b47c90c0451354e25141f`. The
archive verifier confirmed that its migration resources exactly matched the
source `.sql` allowlist, with no backup file, and the isolated packaged-app
smoke test passed. This local build is validation evidence only, not a release
asset. The public release must use the separately generated and verified
tagged-workflow artifact.
