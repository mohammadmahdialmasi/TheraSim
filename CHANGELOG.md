# Changelog

Notable project changes are recorded here. There is no formal application
release or release tag yet. The `Unreleased` section records current
development work and is not a published release. The first formal source
release may use version `0.1.0`, subject to final release-readiness
verification; no definitive release date has been assigned.

## Unreleased

### Added

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
- Complete Persian/English localization and full responsive/accessibility
  verification remain outstanding. Frontend component tests are incomplete;
  no frontend test runner is currently configured, and populated chart states
  lack dedicated component tests.
- Clean-machine installation has not been verified. Windows desktop packaging
  and an installer are not implemented.
- Passing automated software tests does not constitute a security audit or
  establish clinical or psychometric validity. Use synthetic data only.
