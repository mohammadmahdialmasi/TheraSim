# TheraSim — Implementation Baseline

**Baseline Version:** 0.1
**Status:** Initial Implementation Decisions
**Date:** 2026-11-15

## Current Verified Implementation Status — 2026-11-17

This section is the current status summary. The dated implementation
checkpoints below are archival records that preserve the state and verification
reported at those times. Older statements that a feature was absent or
unavailable, including evaluator and analytics capabilities, describe earlier
states and are superseded where this section or later checkpoint details
document subsequent implementation. Earlier decision/specification documents
may likewise retain historical implementation statements; use this current
status and the later checkpoints below when describing the implemented
application. For example, the earlier evaluator-status statement in
`docs/MVP_DECISIONS.md` is superseded by the evaluator implementation checkpoints
below. Historical test counts are not current test results.

TheraSim is an experimental, local-first FastAPI and React research/educational
prototype for fictional ACT simulation. Runs and sequential sessions persist
in SQLite; Ollama and LM Studio are optional local inference providers. ACT is
the only runnable modality.

Character identity and review-gated state transitions are implemented.
Behavioral/emotional event proposals and evidence-linked longitudinal memory
proposals, consolidation, retrieval, and review are present, with deterministic
and model-assisted components bounded by available evidence. These components
do not establish psychological realism or validated memory behavior.

Versioned treatment plans support human-supervised revisions and review.
Guidance is limited to available evidence sources; autonomous clinical
treatment adaptation is not implemented or claimed.

Separate experimental ACT session and longitudinal evaluators are available
when a compatible local model is configured. Raw competency observations
preserve rubric ID/version/hash, confidence, transcript evidence references,
and explicit missing/non-evaluable reasons. Authenticated append-only human
evaluation reviews are implemented. The evaluators validate output structure
and transcript references, but semantic evidence validity is unestablished;
ACT rubrics are not clinically or psychometrically validated. Independent
evaluator validation remains necessary.

Run analytics use persisted data and provide descriptive counts,
rubric-compatible raw numeric rating-code comparisons, an exploratory
evidence-linked chart, and JSON export. They are not validated competency
trends or clinical outcomes.

Paired SQLite backup and restore are implemented; encrypted backups are
optional and do not encrypt live database files. Local single-reviewer
authentication, API authorization, and persistent login throttling are
implemented. Automated retention, live database encryption at rest,
multi-user roles, and password recovery are not implemented. Encrypted
backups do not replace filesystem/device protection.

Persian and English are available in parts of the interface, but complete
Persian/English localization is outstanding. Full responsive and accessibility
verification is outstanding. Clean-machine installation has not been
verified; Windows desktop packaging is not implemented. No frontend test
runner is currently configured, frontend automated component tests are
incomplete, and populated chart states lack dedicated automated component
tests.

The latest reported verification checkpoint identified for this status was
**445 Backend tests passed**, with Frontend lint, the Frontend production
build, and `git diff --check` reported as passing. These are historical
reported results, not tests rerun for this documentation update. Passing
software tests does not establish clinical validity or constitute an
independent security audit.

Use synthetic data only. TheraSim is not production-ready or clinically
validated.

---

## 1. Decision Authority

MVP_DECISIONS.md is the authoritative product and implementation scope document. It takes precedence over conflicting provisional statements in earlier architecture documents.

## 2. Initial Product Scope

- One fully fictional case: AVA-001.
- Acceptance and Commitment Therapy (ACT).
- A variable number of sequential sessions per simulation run; there is no universal session-count cap.
- Persian-first end-to-end workflow.
- Local single-user execution.
- Educational simulation only.
- No real-client records, diagnosis, autonomous psychotherapy, or professional certification claims.

## 3. Architecture

The MVP uses a modular monolith.

Two primary LLM agents:
- Patient Agent.
- Evaluator Agent.

Internal deterministic-first services:
- Orchestrator.
- Patient Context Service.
- Event Processing Service.
- Clinical State Engine.
- Memory Service.
- Evaluation Service.

The leased MemoryExtractionAgent worker is an optional secondary model
execution. Its runs use the shared model-execution ledger; deterministic
evidence validation and review remain authoritative.

## 4. Technology Baseline

- Backend: Python and FastAPI.
- Data validation: Pydantic 2.x.
- Persistence: SQLite.
- Local model runtime: Ollama.
- Frontend: React.
- Testing: Pytest.
- API style: Versioned REST.
- Initial interaction processing: Synchronous HTTP.
- Streaming and cloud model APIs: Deferred.

The initial database implementation will use Python's sqlite3 module, explicit repository interfaces, and versioned SQL migration files. The operational and restricted databases will use separate migration histories.

## 5. Database Separation

Operational database: therasim.db

Restricted case database: case_vault.db

SQLite foreign keys apply within each database. Cross-database relationships must be checked by application services.

Separate files provide logical separation, not complete operating-system security.

The Evaluator Agent must never receive a restricted database connection.

## 6. Agent Boundaries

Patient Agent receives only an explicitly constructed PatientContext.

Evaluator Agent receives only:
- Finalized transcript data.
- Applicable rubric and version.
- Therapist-visible context.
- Explicit evaluation instructions.

The Evaluator Agent must not receive hidden case formulation, undisclosed facts, private state variables, Patient Agent prompts, or future disclosure plans.

No LLM may directly modify canonical clinical state.

## 7. Session and Transcript Rules

- Session numbers start at 1 and increase sequentially without a universal upper limit.
- A later session requires the immediately preceding session to be completed.
- Transcript versions are positive integers beginning at 1.
- Completed transcript versions are immutable.
- Corrections require a new version.
- Transcript hashes use SHA-256 over a canonical UTF-8 JSON representation of chronologically ordered transcript messages.
- Message submission uses an Idempotency-Key scoped to the session.
- Repeated requests must not create duplicate persisted interaction effects.

## 8. ACT Rubric Versions

Session-level rubric:
- ID: ACT_RUBRIC_V0
- Version: 0.2

Longitudinal rubric:
- ID: ACT_LONGITUDINAL_RUBRIC_V0
- Version: 0.2 (count-agnostic; version 0.1 is historical)

The two evaluation scopes remain separate. No unsupported combined score is permitted.

## 9. Clinical State Rules

Initial variables:
- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Values use the simulation range 0–4 and are not validated psychological measurements.

The initial state snapshot is created before the first interaction.

Automatic state changes remain disabled until operational behavioral anchors and versioned transition rules have been reviewed. LLM-generated transition proposals are not authoritative.

## 10. Disclosure Rules

Patient Agent disclosure annotations are proposals only.

The backend must validate case fact identifiers, case version, source message, evidence span, and disclosure policy.

LLM output or keyword matching alone must not establish confirmed disclosure.

Ambiguous disclosures remain candidate_disclosed or requires_review.

## 11. Longitudinal Memory

The Memory Service accepts structured proposals only after a persisted,
completed interaction. It validates Run ownership, chronology, patient-authored
evidence for client-fact classes, and exact quoted transcript spans. Candidates
remain `requires_review` until an explicit decision; accepted revisions
atomically supersede their active predecessor, and review records are immutable.

Successful interactions atomically enqueue a durable memory-extraction job.
The background MemoryExtractionAgent sees only that completed therapist/patient
exchange; validated output is saved for safe replay, and evidence-checked
candidates remain inactive until review. The local worker uses leases, bounded
retries, backoff, and sanitized status reporting. Front-end review controls are
integrated. The original implementation recorded
`unverified_local_caller`; the subsequent local-authentication checkpoint below
supersedes that reviewer-attribution limitation. Therapist hypotheses must
not be converted into confirmed client facts, and active accepted memory is
the only memory eligible for PatientContext retrieval.

PatientContext retrieval deterministically ranks active memories using
current-turn token overlap, source-session recency, confidence, evidence
support count, and memory scope. Unrelated episodic memories with no lexical
overlap are omitted. This is not semantic retrieval. Migration
`015_memory_consolidation_provenance` adds deterministic cross-session
related/repeated/potential-contradiction suggestions and reviewer-authored
consolidation proposals. Proposals remain inactive until authenticated review;
original memories and transcript evidence are preserved through immutable
source links. The text heuristic does not verify clinical meaning, resolve
contradictions, or automatically change existing memory.

The post-interaction extractor can propose behavioral/emotional events and
character-state transitions. Exact evidence quotes must match patient-authored
messages in that interaction; events are persisted as `requires_review`, and
state transitions pass through the existing review-gated transition service.
Extraction jobs pin the Run's character-state snapshot at enqueue time so
delayed processing cannot observe state created after the source interaction.
Migration `011_memory_extraction_state_context` adds the nullable snapshot
reference. Existing jobs with no snapshot remain compatible for memory/event
replay, but state-transition proposals require a pinned snapshot. The sessions
workspace and Run-scoped endpoints expose event proposals, source excerpts,
and rationale-based review. Cross-session memory consolidation remains
unimplemented. Migration `012_event_review_history` adds append-only event
decisions and prevents event status changes without a matching review record.
The initial version recorded `unverified_local_caller`; authenticated local
reviewer attribution is implemented in migration 014.

Migration `013_versioned_treatment_plans` adds immutable Run-scoped plan
revisions and append-only review records. An initial plan is explicitly
authored; subsequent revisions cite same-Run evidence and remain pending until
accepted or rejected. Acceptance atomically supersedes the prior active
revision. The sessions workspace can create an initial plan, add a goal to a
proposed revision using accepted event evidence, and review pending revisions.
This is not an automatic adaptation engine: the system does not infer progress,
setbacks, or intervention effectiveness.

## 12. Local Model Execution

Ollama is the initial model provider.

Model identifiers are independently configurable for Patient and Evaluator agents. The initial MVP may use one compatible model sequentially.

Specific model selection is deferred until controlled compatibility and performance testing.

No external model API is required for core functionality.

## 13. Testing and Acceptance

The implementation must include:
- Unit tests.
- Integration tests.
- API contract tests.
- Session lifecycle tests.
- Agent input/output validation tests.
- State integrity tests.
- Disclosure and information isolation tests.
- Prompt injection tests.
- Persian behavioral tests.
- Reproducibility and model execution metadata tests.

Critical information leakage, invalid state mutation, invalid evidence references, and duplicate persisted interactions are release-blocking failures in the defined test suite.

Passing software tests does not establish clinical validity or educational effectiveness.

Historical checkpoint: 368 Backend tests passed before the evaluator
availability correction in this revision. See the latest verification record
at the end of this document.

## 14. Deferred Features

- English localization.
- Multi-user collaboration.
- Voice and video.
- Cloud model providers.
- Streaming interaction.
- Multiple synthetic clients.
- Real-client data.
- Automatic semantic disclosure confirmation.
- Learned state transition policies.

## Verified implementation checkpoint — 2026-11-17

**Archival checkpoint:** The statements below record the implementation and
verification state at this checkpoint. In particular, its statements that
analytics were outstanding are superseded by the current status above and the
later analytics checkpoint below; do not treat them as current capability
claims.

The shared session lifecycle supports any positive sequential session number. Runs can be completed after one or more sessions when every created session is completed; numbering gaps and incomplete sessions remain invalid. Migration `006_unbounded_session_numbers` removes the legacy SQLite ceiling without rewriting applied migration history and preserves existing session references and transcript-integrity triggers. Successfully persisted interactions atomically record factual therapist-message and generated-patient-response events linked to their source messages and enqueue one memory-extraction job. Migration `007_memory_review_lifecycle` adds quote-span provenance, immutable reviews, rejection state, and explicit supersession lineage. Migration `008_memory_extraction_outbox` adds durable leased jobs and replayable validated output. Migration `009_memory_extraction_model_component` records memory-extraction attempts in the shared model-run ledger. Migration `010_versioned_run_protocols` persists immutable protocol, planning-policy, and session-rubric identifiers per Run. `011_memory_extraction_state_context` pins the character-state snapshot visible at interaction time to each memory-extraction job. `012_event_review_history` records append-only decisions for extracted event proposals.

Historical verification at this checkpoint: 368 Backend tests passed,
Frontend type-check/build and ESLint passed, and browser QA exercised the
bilingual memory review panel at 1920, 1440, 1280, 1024, 768, and 390 CSS
pixels. These results predate the current evaluator and launcher changes.

The internal MemoryService validates candidates against completed interactions, source-Run ownership, chronology, patient-authored evidence for automatic extraction, and exact quoted excerpts. Candidates remain inactive until accepted; rejection is retained, and accepted revisions supersede prior active versions atomically. The API exposes candidate creation, evidence retrieval, review decisions, and sanitized extraction-job status. The sessions workspace now includes Run-scoped candidate review with source quotations, rationale, accept/reject actions, and a clear warning that the local reviewer identity is unverified.

The Run stores protocol `ACT_EDUCATIONAL_SIMULATION` 0.1, the selected planning policy, and session rubric `ACT_RUBRIC_V0` 0.2. This is a versioned educational simulation configuration, not a complete treatment protocol. `ACT_LONGITUDINAL_RUBRIC_V0` 0.2 is count-agnostic; version 0.1 remains the historical three-session example. Full localization and analytics remain outstanding. Automated clinical competency scoring is not implemented or claimed; the experimental session evaluator provides formative educational feedback only.

## Implementation update: pluggable local LLM runtimes and GUI

This section supersedes the earlier Ollama-only runtime decision.

### Local LLM providers

- TheraSim supports two selectable local inference providers: Ollama and LM Studio.
- The initial shared integration target is the OpenAI-compatible Chat Completions API.
- Ollama compatibility is treated as an adapter-specific integration because its OpenAI compatibility is documented as experimental.
- Provider base URLs, model identifiers, and API credentials are configuration values, not hardcoded application logic.
- Provider URLs accept HTTP(S) only and reject user-info, query strings, and fragments. The provider catalog returns the origin only, not URL paths or credentials.
- Initial defaults:
  - Ollama: `http://127.0.0.1:11434/v1`
  - LM Studio: `http://127.0.0.1:1234/v1`
- The first implementation selects one provider at a time through `THERASIM_LLM_PROVIDER`.
- Provider-specific adapters must isolate API differences and be tested independently.
- Core functionality remains local-first; no cloud model API is required.

### Frontend architecture

- The future frontend will use React and TypeScript.
- The interface will be Persian-first and right-to-left (RTL).
- The frontend communicates with the FastAPI backend through versioned API routes.
- The frontend must not connect directly to Ollama or LM Studio.
- Provider selection will eventually be exposed through the backend to the GUI.
- Streaming, live session rendering, and advanced interaction will be implemented after the basic request/response workflow is stable.
- CORS must use explicit trusted frontend origins; wildcard origins are not the default.

### Documentation references

- LM Studio OpenAI-compatible endpoints: https://lmstudio.ai/docs/developer/openai-compat
- Ollama OpenAI compatibility: https://ollama.readthedocs.io/en/openai/
- LM Studio local API quickstart: https://lmstudio.ai/docs/developer/rest/quickstart

## Verified implementation checkpoint — 2026-11-16

### Backend foundation

- Python 3.13 virtual environment created.
- FastAPI application initialized.
- Pydantic 2 request validation enabled.
- Uvicorn local server configured.
- Dependency manifest and resolved dependency lock file added.

### Local LLM integration

- Shared OpenAI-compatible HTTP client implemented.
- Ollama and LM Studio provider configurations implemented.
- Provider model discovery endpoint implemented.
- Chat completion endpoint implemented.
- Provider credentials, URL paths, and URL user-info are excluded from provider catalog responses.
- Empty model lists are handled without treating them as server errors.
- Empty final model responses are rejected.
- Model-provider failures are translated into API errors.

### Verified API routes

- `GET /health`
- `GET /api/v1/llm/providers`
- `GET /api/v1/llm/models/{provider_name}`
- `POST /api/v1/llm/chat`

### Verification results

- Automated backend tests: 14 passed.
- Ollama real local inference: successful.
- LM Studio real local inference: successful.
- Persian UTF-8 response verified through the backend.
- Both local providers returned non-empty responses through TheraSim.

## Verified architectural gaps — 2026-11-17

- Run records preserve case version, modality, language, application configuration version, protocol, planning policy, and session rubric versions. Human-authored plan versions and evidence-linked, review-gated revisions exist; automatic longitudinal adaptation is not implemented.
- Interaction persistence records factual message events and durable memory-extraction jobs atomically. The optional extractor proposes evidence-linked behavioral events; they remain review-pending until explicitly accepted or rejected.
- MemoryExtractionAgent and MemoryService generate and validate review-pending candidates with bounded retries and safe output replay. The sessions UI includes review controls. The initial reviewer sentinel has been superseded by authenticated local-user attribution.
- Evaluation persistence, machine-readable rubric documents, API routes, and separate local-model-backed session and longitudinal Evaluator Agents exist. Both report types remain experimental. Migration `017_evaluation_reviews` adds authenticated, append-only reviewer decisions and feedback without mutating generated reports; raw comparisons remain experimental and do not establish score validity.
- The sessions workspace includes session and run-level evaluations, transcript evidence inspection, memory/event review, treatment-plan workflows, and a persisted-data Run analytics/JSON export. Analytics lists raw session-level competency observations grouped by rubric ID, version ID, and content hash, with confidence, missing-session reasons, evidence-message IDs, and review decisions. The UI provides completed-session range filters and a linked chart of raw numeric rating codes for one exact rubric version/hash, alongside evaluable, non-evaluable, missing, evidence-coverage, confidence, and review-decision summaries. No ratings are averaged or interpreted as clinical outcomes; the displayed code difference is descriptive only and does not establish evaluator validity. Deterministic adaptation guidance reviews only new accepted event evidence and requires a human-authored, evidence-linked plan revision; it does not infer outcomes or select interventions. Complete bilingual/RTL support and responsive verification of the full workflow remain outstanding.
- Fresh setup is supported by `python -m app.persistence.cli`, which initializes both databases and idempotently seeds AVA-001; tests cover repeat seeding and conflicting content. API startup initializes databases but does not itself seed the case.
- The requested `THERASIM_PROJECT_BRIEF_FOR_COPILOT_20261117.md` and `THERASIM_AUDIT_REPORT_20261117.md` files are absent from the workspace.

These results establish technical integration only. They do not establish clinical validity, therapeutic effectiveness, or professional competency measurement validity.

## Current implementation checkpoint — 2026-11-17

- The session lifecycle supports any positive sequential number. Planning-policy identifiers are persisted; treatment plans have immutable revisions and an approval workflow. A deterministic guidance endpoint categorizes new accepted events for human review, while plan changes remain explicit, human-authored proposals.
- A versioned backend modality registry is used by run validation. ACT is the only runnable modality and is marked partial; other approaches remain unavailable, and registry registration alone does not make a modality runnable.
- Paired SQLite backup and restore use exclusive locks, integrity checks, checksums, and no-overwrite publication. An opt-in encrypted backup format uses AES-256-GCM and scrypt-derived passphrase keys; plaintext database copies are not placed in encrypted backup directories. Backups remain unencrypted by default for compatibility. Live database encryption at rest and automated retention are not implemented.
- Migrations `014_local_authentication` and `016_local_login_throttling` add an additive, single-reviewer account/session store and persistent per-client login throttling. Password hashes use scrypt, only token hashes and client-address hashes are stored, all data-bearing API routers require authentication, and reviewer actions store the authenticated local account ID. The browser keeps the bearer token in `sessionStorage`. Password reset, multi-user roles, live-database encryption at rest, and automated retention remain unimplemented.
- The memory- and event-review UI and durable extraction worker are present.
  Review attribution is tied to the authenticated local account;
  deterministic evidence-preserving consolidation proposals now require review.
- Session evaluation uses a separate experimental Evaluator Agent when a local model is configured. It validates the exact competency set, therapist-message references, and excerpt spans, then persists immutable `requires_review` revisions with transcript/rubric hashes and evaluator model-run provenance. This does not establish that the quoted evidence semantically supports a rating or that the rubric is clinically or psychometrically valid. With no configured model, generation returns `503 evaluator_unavailable_experimental`; invalid output returns `502` and creates no evaluation report. Historical records without an Evaluator Agent model-run identifier are returned as experimental with placeholder items and evidence withheld.
- The longitudinal rubric version 0.2 is count-agnostic; version 0.1 remains a historical three-session rubric. Run-level evaluation requires at least two completed ACT sessions and evaluates all completed sessions in chronological order. Scored competencies require exact therapist-message evidence spanning at least two sessions; reports preserve immutable revisions, transcript hashes, rubric/prompt/model provenance, and a Run-session snapshot. Session creation, status changes, or completed transcript changes make prior longitudinal reports stale. Reports appear in the sessions workspace with evidence excerpts and original-message inspection. Authenticated reviewers can append acceptance or revision-request feedback; the review record is immutable and does not alter report ratings. The work remains experimental and does not establish semantic score validity or clinical/psychometric validity. Run analytics expose raw rubric-version-scoped session observations, not clinical outcomes or computed competency trends.
- Run analytics range summaries and charts are derived from persisted API observations, scoped to one rubric-version/content-hash/competency group and selected completed sessions. Missing and NE observations are excluded from numeric comparisons, never zero-filled, and shown as separate counts. Plot line segments stop at nonconsecutive sessions, and data points link to their evaluation records. The chart and raw code differences are exploratory descriptive analytics, not validated trends or competency measurements; detailed definitions are in `docs/ANALYTICS.md`.
- `START_THERASIM.bat`, `STOP_THERASIM.bat`, and `CHECK_THERASIM.bat` run the development Backend and Frontend, use safe migrations, and track process identity. They have not yet been validated through a clean-machine installation.

Verification for this checkpoint: **377 Backend tests passed**; Frontend
`npm run lint` and `npm run build` passed. The launcher passed its prerequisite
check and an isolated startup/shutdown exercise: it migrated and seeded
temporary databases, served Backend health and the Vite page, stopped its
tracked processes, and left the workspace databases untouched. PowerShell
syntax parsing and `git diff --check` passed. Dependency installation on a
clean machine, model-driven UI interaction, and desktop packaging were not
tested. Initial test commands from the repository root failed due to incorrect
working directories/tool PATH; the corrected Backend and Frontend commands
passed.

## Evaluator implementation checkpoint — 2026-11-17

The ACT session evaluator is a separate, local-model-backed component. Its
machine-readable `ACT_RUBRIC_V0` competency contract is checked against the
versioned Markdown rubric. Structured output is strictly validated; scored
competencies require exact therapist-authored transcript excerpts and valid
message IDs, while `NE` requires missing-evidence details. Reports are
persisted with immutable revisions, a transcript manifest/hash, rubric hash,
prompt/model provenance, and `requires_review` status. Invalid model output
does not create an evaluation report, and evaluator failures are recorded in
the model-run ledger. Historical placeholder scores remain withheld.

The session workspace includes an evaluation panel for report history,
competency results, confidence, limitations, and transcript-linked evidence.
Focused evaluator verification: **17 tests passed**; full Backend suite:
**408 tests passed at that checkpoint**. At that point, longitudinal
evaluation, review/approval workflow, and a standalone evaluation dashboard
were not implemented. See the subsequent longitudinal evaluator checkpoint
below for the current run-level evaluation capability.

## Longitudinal evaluator implementation checkpoint

The separate Run-level ACT evaluator requires at least two completed
sessions, evaluates every completed transcript in order, and requires every
scored competency to cite exact therapist-authored message excerpts from at
least two sessions. `NE` is retained for insufficient evidence. Reports are
immutable, review-required revisions with transcript manifests and hashes,
rubric and prompt versions, model provenance, exact session scope, and a
snapshot of all Run sessions. Later session creation, session-status changes,
or included transcript changes mark prior reports stale; a Run that already
has an in-progress session at evaluation time is not falsely marked stale.
The sessions workspace presents longitudinal reports, session references,
source excerpts, and the original cited message content.

This validation checks structural and exact-quote correctness, not semantic
evidence support or clinical/psychometric validity. The feature remains
experimental; password reset, persistent login throttling, independent
analytics, and cross-session evaluation comparisons remain outstanding.

Verification after this work: **430 Backend tests passed**; Frontend ESLint,
TypeScript/production build, and `git diff --check` passed.
