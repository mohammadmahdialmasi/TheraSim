# Changelog

Notable project changes are recorded here. GitHub Release v0.2.0 is published
and its tag and assets are immutable; the Windows ZIP contains an unintended
ignored migration backup. The v0.2.1 patch corrects the packaging allowlist.
Zenodo v0.1.0 remains a documentation-only archive, not an executable source
release.

## v0.3.1 — Release consistency update

- Align active application, frontend, packaging, workflow, documentation, and
  validation metadata to `0.3.1`.
- Repaired the Windows package verifier's legacy C# console/process bridge,
  added archive traversal guards and explicit failure exits, and verified the
  public v0.3.1 ZIP under Windows PowerShell 5.1 and PowerShell 7.
- Added reusable evidence privacy/redaction utilities and tests, and separate
  sanitized evidence exports. Corrected benchmark documentation to distinguish
  the 2026-11-22 rerun from earlier historical runs.
- Preserve the immutable `v0.3.0` release history and existing historical
  changelog and DOI records.
- Strengthen CI with an automated release-version consistency check.
- Update and verify the Windows x64 portable package workflow.

## v0.3.0 — Local-first model configuration and release hardening

- Add per-provider patient-agent and evaluator-agent model overrides with a
  general-model fallback, and keep evaluator report, rubric, transcript, and
  exact-quote validation in the application regardless of provider output
  constraints.
- Add optional hardware inventory and document measured, model-specific
  synthetic workflow results without claiming compatibility across devices
  or recommending an ACT evaluator model.
- Add bilingual provider settings, user-reviewed support diagnostics, and a
  manual update check that verifies official release metadata without
  downloading or installing files.
- Protect saved Windows provider keys with the current user's DPAPI context;
  keep environment-variable precedence and document non-Windows credential
  limitations.
- Unify the Windows x64 portable ZIP name, migration allowlist verification,
  checksum/manifest generation, and isolated package smoke test.
- Add bilingual installation and user guides. Continue to require synthetic
  data and make no clinical, psychometric, or therapeutic efficacy claims.

## v0.2.1 — Corrective patch

- Restrict the Windows package to explicit `.sql` migration files and verify
  the archive contains exactly the source migration allowlist, with no backup
  files.
- Run backend tests against an isolated temporary data directory in CI and
  update package names and application version metadata to `0.2.1`.
- Complete Persian labels for persisted feature statuses, improve mixed
  direction handling for user/model text and identifiers, and keep Persian
  interface errors localized.
- Add bilingual installation and release guidance. The v0.2.0 release remains
  unchanged; publish v0.2.1 only after the tagged Windows workflow and its
  generated package have been verified.

## v0.2.0

### Added

- Added a bilingual project landing page and authentic application screenshots
  using fictional demonstration data.
- Added a versioned least-privilege Patient Agent model-input projection that
  excludes hidden formulation, undisclosed or review-pending facts,
  model-generated memory summaries, and internal state.
- Implemented separate experimental ACT session and longitudinal Evaluator
  Agents. They require a configured local model, validate rubric coverage and
  transcript references/quotes, preserve rubric and transcript provenance,
  and withhold invalid model output. Exact-reference validation does not
  establish semantic evidence support.
- Added authenticated, append-only human evaluation reviews and review
  provenance without modifying generated evaluation reports.
- Added local single-reviewer authentication, bearer-session authorization,
  persistent login throttling, and authenticated reviewer attribution for
  review workflows.
- Added raw competency observations scoped to rubric ID, version, and content
  hash, with confidence, evidence references, explicit missing/non-evaluable
  reasons, and review-decision provenance.
- Added character identity and review-gated state-transition proposals, plus
  evidence-linked longitudinal memory proposals, consolidation, retrieval, and
  review workflows.
- Added versioned treatment plans with human-authored, evidence-linked
  revisions and explicit approval/rejection history. Guidance remains
  human-supervised and limited to available evidence sources.
- Added persisted Run-level descriptive analytics, session-range raw
  rating-code comparisons within compatible rubric scopes, an exploratory
  evidence-linked chart, and JSON export.
- Added paired SQLite backup and restore, plus optional AES-256-GCM encrypted
  backups using scrypt-derived passphrase keys.
- Added Windows development launchers with process ownership checks, safe
  initialization, logs, health checks, and shutdown support.
- Added a one-folder Windows executable build with a same-origin local UI,
  user-local SQLite storage and logs, allow-listed user configuration, a
  smoke-test script using an isolated temporary account, and a Windows CI
  workflow. The package contains no language-model weights and is not an
  installer.
- Added English/Persian translations for the ACT registry and aligned visible
  application version metadata to 0.2.0.
- Added Windows build/install instructions and contributor, support,
  security-reporting, and community-standards policies.

### Security and dependencies

- Updated the cryptography requirement and lock to `50.0.2` after the previous
  locked version was reported vulnerable by pip-audit.
- Updated the compatible frontend lint dependency graph in the lockfile;
  npm audit then reported no vulnerable packages.

### Limitations and release notes

- ACT remains the only runnable modality. The ACT rubrics and evaluators are
  experimental; semantic evidence validity, clinical validity, psychometric
  validity, and independent evaluator reliability have not been established.
- Analytics are exploratory descriptions of persisted records, not validated
  competency trends or clinical outcomes. No overall score is calculated.
- Treatment-plan guidance does not autonomously adapt treatment or select
  clinical interventions.
- Authentication is single-reviewer. Multi-user roles, password recovery,
  automated data retention, and live database encryption at rest are not
  implemented. Encrypted backups are optional and do not encrypt live
  database files.
- Comprehensive accessibility verification remains outstanding. Frontend
  component tests are incomplete;
  no frontend test runner is currently configured, and populated chart states
  lack dedicated component tests.
- Broad clean-device usability has not been independently reviewed. A
  one-folder Windows package is implemented; an installer is not provided.
- Passing automated software tests does not constitute a security audit or
  establish clinical or psychometric validity. Use synthetic data only.
- Patient Agent output validation checks JSON structure, not semantic
  disclosure safety. The reduced model input is a data-minimization control,
  not a guarantee against unsafe generated text.
