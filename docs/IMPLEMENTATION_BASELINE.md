# TheraSim — Implementation Baseline

**Baseline Version:** 0.1
**Status:** Initial Implementation Decisions
**Date:** 2026-11-15

## 1. Decision Authority

MVP_DECISIONS.md is the authoritative product and implementation scope document. It takes precedence over conflicting provisional statements in earlier architecture documents.

## 2. Initial Product Scope

- One fully fictional case: AVA-001.
- Acceptance and Commitment Therapy (ACT).
- Exactly three sequential sessions per simulation run.
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

Event Processing and Memory are not independent mandatory LLM agents.

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

- Session 1, 2, and 3 must be sequential.
- Later sessions require earlier sessions to be completed.
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
- Version: 0.1

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

Initial memory is structured and deterministic-first.

Every memory item must preserve:
- Information class.
- Source message references.
- Originating session.
- Version and status.

Therapist hypotheses must not be converted into confirmed client facts.

Free-form LLM memory summaries are deferred from the first implementation.

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
- Automated clinical competency scoring.

These require separate decisions and validation before implementation.
