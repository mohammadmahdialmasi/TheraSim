# TheraSim — Implementation Baseline

**Baseline Version:** 0.1
**Status:** Initial Implementation Decisions
**Date:** 2026-11-15

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
retries, backoff, and sanitized status reporting. Front-end review controls are integrated. Since the single-user API has no authentication, it rejects
client-supplied reviewer identifiers and records `unverified_local_caller`;
this is explicitly not a verified human identity. Therapist hypotheses must
not be converted into confirmed client facts, and active accepted memory is
the only memory eligible for PatientContext retrieval.

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

The shared session lifecycle supports any positive sequential session number. Runs can be completed after one or more sessions when every created session is completed; numbering gaps and incomplete sessions remain invalid. Migration `006_unbounded_session_numbers` removes the legacy SQLite ceiling without rewriting applied migration history and preserves existing session references and transcript-integrity triggers. Successfully persisted interactions atomically record factual therapist-message and generated-patient-response events linked to their source messages and enqueue one memory-extraction job. Migration `007_memory_review_lifecycle` adds quote-span provenance, immutable reviews, rejection state, and explicit supersession lineage. Migration `008_memory_extraction_outbox` adds durable leased jobs and replayable validated output. Migration `009_memory_extraction_model_component` records memory-extraction attempts in the shared model-run ledger. Migration `010_versioned_run_protocols` persists immutable protocol, planning-policy, and session-rubric identifiers per Run.

Historical verification at this checkpoint: 368 Backend tests passed,
Frontend type-check/build and ESLint passed, and browser QA exercised the
bilingual memory review panel at 1920, 1440, 1280, 1024, 768, and 390 CSS
pixels. These results predate the current evaluator and launcher changes.

The internal MemoryService validates candidates against completed interactions, source-Run ownership, chronology, patient-authored evidence for automatic extraction, and exact quoted excerpts. Candidates remain inactive until accepted; rejection is retained, and accepted revisions supersede prior active versions atomically. The API exposes candidate creation, evidence retrieval, review decisions, and sanitized extraction-job status. The sessions workspace now includes Run-scoped candidate review with source quotations, rationale, accept/reject actions, and a clear warning that the local reviewer identity is unverified.

The Run stores protocol `ACT_EDUCATIONAL_SIMULATION` 0.1, the selected planning policy, and session rubric `ACT_RUBRIC_V0` 0.2. This is a versioned educational simulation configuration, not a complete treatment protocol. `ACT_LONGITUDINAL_RUBRIC_V0` 0.2 is count-agnostic; version 0.1 remains the historical three-session example. The Evaluator Agent, full localization, and analytics remain outstanding.
- Automated clinical competency scoring.

These require separate decisions and validation before implementation.

## Implementation update: pluggable local LLM runtimes and GUI

This section supersedes the earlier Ollama-only runtime decision.

### Local LLM providers

- TheraSim supports two selectable local inference providers: Ollama and LM Studio.
- The initial shared integration target is the OpenAI-compatible Chat Completions API.
- Ollama compatibility is treated as an adapter-specific integration because its OpenAI compatibility is documented as experimental.
- Provider base URLs, model identifiers, and API credentials are configuration values, not hardcoded application logic.
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
- Provider credentials are excluded from provider catalog responses.
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

- Run records preserve case version, modality, language, application configuration version, protocol, planning policy, and session rubric versions. Planning policies are recorded configuration, not an executing treatment-planning engine.
- Interaction persistence records factual message events and durable memory-extraction jobs atomically. Behavioral event extraction remains unimplemented.
- MemoryExtractionAgent and MemoryService generate and validate review-pending candidates with bounded retries and safe output replay. The sessions UI includes review controls, but reviewer identity is unauthenticated.
- Evaluation persistence, rubric documents, service reads, and API routes exist. The Evaluator Agent is not implemented; generation requests now fail explicitly, and historical deterministic placeholder reports are exposed as experimental without their scores or evidence.
- The dedicated frontend feature modules currently cover sessions only; evaluation, analytics, complete bilingual/RTL support, and responsive screen verification remain outstanding.
- Fresh setup is supported by `python -m app.persistence.cli`, which initializes both databases and idempotently seeds AVA-001; tests cover repeat seeding and conflicting content. API startup initializes databases but does not itself seed the case.
- The requested `THERASIM_PROJECT_BRIEF_FOR_COPILOT_20261117.md` and `THERASIM_AUDIT_REPORT_20261117.md` files are absent from the workspace.

These results establish technical integration only. They do not establish clinical validity, therapeutic effectiveness, or professional competency measurement validity.

## Current implementation checkpoint — 2026-11-17

- The session lifecycle supports any positive sequential number. Planning-policy identifiers are persisted, but there is no treatment-planning engine or approval workflow.
- ACT is the only supported modality. Other modalities have no runtime implementations or registry.
- The memory-review UI and durable extraction worker are present. Reviewer identity remains unauthenticated; autobiographical-memory consolidation and behavioral event extraction are incomplete.
- Evaluation generation is disabled because no Evaluator Agent exists. The endpoints return `503 evaluator_unavailable_experimental` without persisting an evaluation. Historical records without an Evaluator Agent model-run identifier are returned as experimental with their placeholder items and evidence withheld.
- The longitudinal rubric version 0.2 is count-agnostic; version 0.1 remains a historical three-session rubric. No longitudinal evaluation, revisions, analytics, or evidence-linked charts are implemented.
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
