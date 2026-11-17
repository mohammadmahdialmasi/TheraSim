# Source Release Readiness Checklist

This checklist records implementation boundaries and verification gates for
public releases. It does not declare the repository production-ready or
clinically validated.

## Status definitions

- **Implemented:** the capability exists in the current application, within
  the stated scope.
- **Partially implemented:** a bounded workflow exists, but important
  functionality or coverage remains absent.
- **Experimental:** the feature is available for research/education, but its
  behavioral, semantic, clinical, or psychometric validity is unestablished.
- **Not implemented:** no working application capability is available.
- **Not verified:** the required check has not been completed in a
  representative environment or against the relevant acceptance criteria.

## Current capability assessment

| Area | Status | Current boundary |
|---|---|---|
| Local application | **Implemented** | FastAPI/React application with SQLite persistence, runs, sequential sessions, and optional local Ollama/LM Studio providers. |
| Modality | **Partially implemented** | Fictional ACT workflow only; ACT is the only runnable modality. |
| Character and memory | **Partially implemented / Experimental** | Evidence-linked state/event and memory proposals are review-gated. Retrieval and consolidation use limited deterministic signals; psychological realism and longitudinal consistency are not independently validated. |
| Treatment plans | **Partially implemented** | Versioned plans and human-supervised revisions exist. Guidance is limited to available evidence sources; autonomous clinical treatment adaptation is not implemented or claimed. |
| Session evaluator | **Experimental** | A local-model-backed ACT evaluator validates output structure and transcript references. Semantic evidence support, clinical validity, psychometric validity, and independent reliability are unestablished. |
| Longitudinal evaluator | **Experimental** | Evaluates completed sessions within a Run with rubric and transcript provenance and staleness tracking. It is not a validated longitudinal competency measure. |
| Human evaluation reviews | **Implemented** | Authenticated, append-only reviewer feedback; it does not convert raw observations into clinically validated scores. |
| Competency observations | **Implemented as raw observations** | Scoped to rubric identity/version/hash with confidence, evidence references, and explicit missing/non-evaluable reasons. They must not be interpreted as validated scores. |
| Run analytics | **Partially implemented / Exploratory** | Persisted-data counts, compatible rubric-scoped raw rating-code comparisons, and an evidence-linked chart. These are descriptive/exploratory, not validated competency trends or clinical outcomes. |
| Authentication | **Partially implemented** | Single local reviewer, API authentication/authorization, and persistent login throttling. Multi-user roles and password recovery are absent. |
| Data protection | **Partially implemented** | Paired SQLite backup/restore; opt-in encrypted backups. Encrypted backups do not encrypt live database files. Automated retention and live database encryption at rest are absent. |
| Localization | **Implemented for current workflows** | English and Persian are available across implemented application workflows; document language and RTL direction switch with the interface. Comprehensive accessibility and screen-reader verification remain outstanding. |
| Responsive/accessibility | **Not fully verified** | A limited viewport check is not full responsive or accessibility verification; representative workflows and keyboard/screen-reader behavior still need assessment. |
| Windows operation | **Implemented / Limited verification** | Development launchers and a one-folder Windows executable target exist. The executable uses loopback, user-local data/logs, no bundled model, and a temporary-data package smoke test. Broad clean-device usability is not independently established. |
| Desktop distribution | **Implemented as a portable package** | A PyInstaller one-folder package and Windows CI workflow are provided. No MSI/installer is provided; package and release binary must be built and verified before publication. |
| Frontend automated testing | **Partially implemented / Not verified** | No frontend test runner is currently configured. Populated chart states lack dedicated automated component tests. |
| Independent validation | **Not implemented** | Independent qualified evaluator review and appropriate empirical validation remain necessary. |

## Before preparing a source archive

- [ ] Review staged, unstaged, and untracked changes; exclude local databases,
  virtual environments, dependency folders, logs, backups, generated output,
  and secrets unless a file is explicitly intended for distribution.
- [ ] Confirm copyright, attribution, mixed-license boundaries, third-party
  notices, and any scenario/material-specific terms.
- [ ] Review README, changelog, citation metadata, installation instructions,
  supported Python/Node versions, and all documented limitations for
  consistency. v0.2.0 is a published, immutable GitHub release; do not move,
  overwrite, delete, or edit its tag or assets.
- [ ] Confirm `CITATION.cff` is valid and does not contain provisional release
  metadata; do not create Zenodo-specific metadata unless it is required and
  approved.
- [ ] Verify a clean source checkout and dependency installation from the
  documented lock files. Record the operating system and runtime versions.
- [ ] Run the complete Backend test suite, Frontend lint and production build,
  Python syntax checks, migration tests on temporary databases, backup/restore
  tests on synthetic data, and `git diff --check`.
- [ ] Exercise isolated local startup, run creation, sequential sessions,
  deterministic fake-model interactions, persistence, shutdown, and restart.
  Do not use or overwrite a user's existing database for testing.
- [ ] Verify that evaluator failures and missing evidence are explicit, that
  raw observations retain rubric/transcript provenance, and that human review
  records remain append-only. Do not present model reports as validated
  assessment.
- [ ] Verify analytics use persisted records, do not mix incompatible rubric
  versions, do not zero-fill missing/NE observations, and label outputs as
  exploratory raw descriptions rather than validated trends.
- [ ] Review loopback binding, API authorization, logging, authentication,
  backups, filesystem controls, dependencies, and threat-model limitations.
  Passing software tests is not an independent security audit.
- [ ] Build and verify the actual Windows ZIP on Windows. The smoke test must
  use a unique temporary data directory and synthetic account; never inspect
  or use a user's existing SQLite contents.
- [ ] Confirm the package includes exactly the intended migration `.sql`
  files from the operational and restricted migration directories. Reject
  backup files, including `.sql.*.bak` artifacts, without deleting local
  copies.
- [ ] Do not claim a clean-machine installation or a Windows installer. The
  distributable is a one-folder portable ZIP, and broader clean-device
  usability remains unverified.
- [ ] Verify the archive contains no user data, local model, `.env`, secrets,
  virtual environment, dependency/build output, or unintended backup files.
- [ ] Confirm the Patient Agent model request includes only public identity,
  authorized disclosures, explicit-disclosure memories, and transcript text;
  document that response-schema validation is not semantic disclosure review.

## Data and validation boundaries

Use fictional and synthetic data only. TheraSim is an experimental
research/educational prototype, not a clinical product. ACT rubrics are not
clinically or psychometrically validated. Evaluator semantic/clinical validity
is unestablished. Independent expert evaluation and empirical validation are
prerequisites for any claims about evaluator reliability, competency
measurement, treatment effectiveness, or psychological realism.

Retention/deletion workflows are not implemented. Automated retention is not
implemented. Encrypted backups are an optional protection for backup copies;
they do not encrypt the live SQLite databases. Choose and test any operational
retention or recovery procedure outside the application, and do not imply that
it is enforced by TheraSim.

## Release status

Zenodo v0.1.0 is a published documentation-only archive (version DOI
`10.5281/zenodo.24244882`; concept DOI `10.5281/zenodo.24244881`). It does
not constitute an executable source release. GitHub Release v0.2.0 is
published and immutable; its Windows ZIP contains an unintended ignored
migration backup. v0.2.1 is the corrective patch version. Push its annotated
tag to trigger the Windows workflow; publish the bilingual GitHub Release
only after that workflow succeeds, its generated ZIP is inspected against the
SQL migration allowlist, and its temporary-data smoke test and checksum are
verified. Use only that workflow-generated artifact; never attach a locally
fabricated package. Releases must not be described as production-ready or
clinically validated.

This document is a readiness aid, not authorization to create a tag, GitHub
Release, or external deposit.
