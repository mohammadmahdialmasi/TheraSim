# TheraSim Service Layer Specification

**Document ID:** THERASIM-SERVICE-LAYER-001
**Version:** 0.1
**Status:** Architecture Draft
**Scope:** Backend Application Services
**Last Updated:** 2026-11-16

---

## 1. Purpose

This document defines the responsibilities, boundaries, dependencies, and transaction rules of the TheraSim Service Layer.

The Service Layer coordinates application use cases and domain operations between the API, repositories, databases, and AI agents.

Its purpose is to keep application logic independent from HTTP routes, database implementation details, frontend behavior, and external model providers.

This document defines architecture and contracts. It does not authorize immediate implementation of all services.

## 2. Architectural Position

The intended dependency direction is:

API Routes
    -> Application Services
        -> Repositories
            -> Database Connections

Application Services may also coordinate:

- Domain validation.
- Authorized context construction.
- Event processing.
- State management.
- Memory management.
- Model provider interfaces.
- Audit recording.

Repositories must not depend on application services or API routes.

AI agents must not receive repository objects or database connections.

The frontend must communicate through the API and must never access SQLite files directly.

## 3. Core Architectural Rules

The following rules are mandatory:

1. API routes must remain thin.
2. Application use cases must be coordinated by services.
3. Repositories must remain persistence-focused.
4. Services own transaction boundaries.
5. Repositories must not independently commit or roll back caller-owned transactions.
6. Model calls must not occur while database write transactions are open.
7. Services must validate application-level relationships across the two databases.
8. Agents must receive explicit data-transfer objects rather than database objects.
9. Restricted information must only cross authorized service boundaries.
10. Domain state must not be mutated solely on the basis of an unrestricted LLM response.
11. Service operations must preserve idempotency where applicable.
12. Failures must not silently discard already persisted user input.

## 4. Database Ownership and Transactions

TheraSim uses two independent SQLite databases:

- Operational database: therasim.db
- Restricted database: case_vault.db

Each database has its own connection and transaction lifecycle.

The DatabaseManager provides database access.

Application services coordinate database operations and pass caller-owned connections to repositories.

Repositories must not:

- Create hidden connections.
- Commit service-owned transactions.
- Close service-owned connections.
- Retain connections between operations.
- Perform network or model calls.

A service operation that uses both databases must explicitly handle the fact that they do not share one atomic transaction.

Cross-database consistency must be enforced through application-level validation and appropriate recovery procedures.

## 5. Service Inventory

The planned service layer contains:

| Service | Primary Responsibility | Priority |
|---|---|---|
| CaseService | Case and case-version operations | High |
| RunService | Simulation run lifecycle | High |
| SessionService | Session progression and lifecycle | High |
| PatientContextService | Authorized patient context construction | Critical |
| DisclosureService | Disclosure validation and history | High |
| InteractionService | Therapist interaction orchestration | Critical |
| EventProcessingService | Evidence-based event processing | High |
| MemoryExtractionWorker | Leased post-interaction proposal jobs | High |
| StateService | State snapshots and transitions | High |
| MemoryService | Longitudinal memory management | High |
| EvaluationService | Evaluation orchestration | Deferred |

The exact implementation order may be adjusted when service dependencies are reviewed.

## 6. CaseService

### Responsibilities

CaseService manages case metadata and case versions in the operational database.

It must:

- Retrieve case information.
- Retrieve available case versions.
- Validate case lifecycle status.
- Validate version ownership.
- Retrieve the corresponding public case profile.
- Prevent invalid case-version references.
- Support controlled case activation and archival operations.

### Boundaries

CaseService must not expose restricted case facts through public case DTOs.

Restricted case profiles and facts must remain in the restricted database.

Case version identity must be validated before creating a simulation run.

## 7. RunService

### Responsibilities

RunService manages simulation run creation and lifecycle.

It must:

- Create a simulation run.
- Validate case and case-version identity.
- Verify required restricted case data exists.
- Validate initial run configuration.
- Retrieve run status.
- Enforce allowed run-state changes.
- Record relevant audit events.

### Cross-Database Validation

Before creating a run, RunService must verify:

1. The case exists in the operational database.
2. The case version belongs to that case.
3. The required restricted case profile exists.
4. The restricted profile identifies the same case and version.
5. The case version is eligible for simulation.

The two databases must not be assumed to share foreign-key enforcement.

Application-level validation is mandatory.

## 8. SessionService

### Responsibilities

SessionService manages a sequential lifecycle with no universal session limit.

It must:
- Create the first and subsequent sessions.
- Enforce sequential session numbering.
- Permit additional sessions after each preceding session is completed.
- Require the previous session to be completed before opening the next session.
- Retrieve session status.
- Enforce allowed session-state transitions.
- Maintain transcript version information.
- Prevent transcript mutation after session completion.

### Session Rules

The intended progression is:

Session 1 -> Session 2 -> ... -> Session N

A session must not be skipped.

A completed session is immutable.

The service must not treat an incomplete or interrupted session as completed.

## 9. PatientContextService

### Responsibility

PatientContextService constructs the explicitly authorized context required by the Patient Agent.

It is the only planned application service authorized to combine relevant restricted case information with operational simulation information for Patient Agent context construction.

### Data Sources

It may access:

- Operational case metadata.
- Public case profile.
- Simulation run.
- Current session.
- Relevant session history.
- Approved disclosure records.
- Restricted case profile.
- Restricted case facts.
- Authorized longitudinal memory.

### Output Contract

The service must return an explicit PatientContext data-transfer object.

The DTO must contain only information required for the Patient Agent to simulate the fictional patient.

It must not contain:

- SQLite connections.
- Repository objects.
- Filesystem access.
- Unrestricted application configuration.
- Unrelated case records.
- Secrets or authentication credentials.

The Patient Agent must not receive direct database access.

### Security Boundary

PatientContext construction must follow case disclosure policy and the intended simulation behavior.

Restricted facts must not be exposed to the therapist-facing interface merely because they were loaded for the Patient Agent.

Evaluator Agent must use a separate context-building boundary and must not receive this restricted PatientContext.

## 10. DisclosureService

### Responsibilities

DisclosureService manages patient fact disclosure records and their history.

It must:

- Validate that a referenced case fact exists in the restricted case vault.
- Validate case, version, and run identity.
- Validate source message ownership.
- Validate evidence offsets.
- Preserve disclosure status history.
- Enforce allowed disclosure status transitions.
- Record supporting evidence.
- Prevent unsupported status confirmation.

### Disclosure Statuses

The supported statuses are:

- not_disclosed
- candidate_disclosed
- confirmed_disclosed
- requires_review

A model-generated interpretation must not automatically become a confirmed disclosure.

Confirmation requires the applicable evidence and validation rules.

The service must preserve the distinction between candidate disclosure and confirmed disclosure.

## 11. InteractionService

### Responsibility

InteractionService orchestrates a complete therapist-to-patient interaction.

It coordinates request validation, persistence, PatientContext creation, Patient Agent invocation, response validation, and final persistence.

It must not delegate database ownership to an AI agent.

### Interaction Lifecycle

The intended lifecycle is:

1. Validate run and session.
2. Validate the idempotency key.
3. Calculate and compare the canonical request hash.
4. Create or retrieve the interaction request.
5. Persist the therapist message exactly once.
6. Commit the initial operational transaction.
7. Build the authorized PatientContext.
8. Invoke the Patient Agent outside any database write transaction.
9. Validate the returned PatientResponse.
10. Persist model execution metadata.
11. Validate deterministic post-response operations.
12. Persist the patient response and applicable events.
13. Finalize the interaction request.
14. Record required audit information.

The exact persistence order must guarantee that the therapist message is not lost when model execution fails.

### Idempotency

Repeated requests with the same session and idempotency key must not create duplicate therapist messages.

If the same key is reused with a different request hash, the service must reject the conflicting request.

Repeated requests with the same key and same hash must return or resume the existing interaction state according to the recovery policy.

### Model Failure

When Patient Agent execution fails:

- The therapist message remains persisted.
- The interaction request remains recoverable.
- The failure is recorded.
- Model execution metadata is recorded where available.
- No fabricated patient response is created.
- The service must not silently mark the interaction as successful.

### Transaction Boundary

No database write transaction may remain open during Patient Agent execution.

The interaction lifecycle must use short, explicit persistence transactions.

## 12. EventProcessingService

### Responsibilities

EventProcessingService handles structured event creation and evidence association.

It must:

- Validate event types.
- Validate run and session ownership.
- Validate source message references.
- Validate evidence offsets.
- Preserve source evidence.
- Support deterministic event processing.
- Distinguish system-generated candidates from confirmed records.

### Processing Policy

Deterministic processing is preferred where applicable.

Model-assisted interpretation may propose candidate events.

Model output must not automatically establish a confirmed clinical fact.

Events must retain references to the evidence supporting them.

## 13. StateService

### Responsibilities

StateService manages state snapshots, state variables, and transition records.

It must:

- Create valid baseline snapshots.
- Validate known state variables.
- Validate variable ranges.
- Preserve snapshot identity.
- Validate transition evidence.
- Support explicit transition resolution.
- Maintain state history.

### Initial State Policy

The initial state variables are engineering parameters for the simulation.

They are not validated psychological measurements.

Automatic semantic state transitions remain disabled until behaviorally anchored rules have been specified and reviewed.

An LLM response alone must not directly mutate canonical state.

State changes must be traceable to explicit evidence and deterministic application rules.

## 14. MemoryService

### Responsibilities

MemoryService manages structured longitudinal simulation memory.

It must support the existing memory classifications:

- confirmed_fact
- explicit_disclosure
- therapist_hypothesis
- system_generated_summary
- reported_outcome
- structured_observation

It must:

- Validate memory classifications.
- Preserve evidence references.
- Preserve source session identity.
- Validate source message ownership.
- Prevent unsupported conversion of hypotheses into confirmed facts.
- Preserve the distinction between reported outcomes and system interpretations.
- Provide relevant memory context through explicit DTOs.

### Lineage Constraint

MemoryExtractionWorker processes durable post-interaction jobs using a separate, versioned MemoryExtractionAgent prompt. Its input is restricted to the completed therapist/patient exchange. The structured output is persisted for replay, then MemoryService validates interaction ownership, Run, chronology, patient-authored exact quotes, and idempotency before storing candidates as inactive `requires_review` items. Model calls never run inside database transactions. Leases recover abandoned jobs; retries use backoff and terminate after five attempts with sanitized status. Review decisions are append-only. Acceptance activates the item; rejection leaves it inactive. Revisions create a new version linked to the active predecessor, and accepting a revision atomically supersedes that predecessor.

The service does not generate proposals, infer facts from transcripts, or claim that a reviewer identity is authenticated. Automatic proposal extraction and the user-facing review workflow remain future integration work.

## 15. EvaluationService

EvaluationService is intentionally deferred until its prerequisites are finalized.

It will eventually coordinate:

- Session-level evaluation.
- Longitudinal run-level evaluation.
- Rubric version selection.
- Transcript version and hash validation.
- Evaluation request idempotency.
- Evaluator input construction.
- Evidence validation.
- Evaluation persistence.

### Mandatory Prerequisites

Before implementation, the architecture must define:

1. A durable evaluation idempotency mechanism.
2. Transcript versioning and immutable evaluation manifests.
3. Explicit session and run evaluation scopes.
4. Evaluator-specific DTOs.
5. Strict separation from restricted patient facts.
6. Evidence excerpts and source references.
7. Handling of uncertainty and insufficient evidence.

SessionEvaluation and RunEvaluation must remain conceptually distinct.

Evaluator Agent must never receive restricted database connections or hidden case facts.

## 16. Data Transfer Objects

Services must communicate using explicit data-transfer objects.

DTOs must:

- Define their fields explicitly.
- Validate input data.
- Avoid unrestricted dictionaries for sensitive contexts.
- Avoid exposing internal database implementation details.
- Distinguish public and restricted data.
- Preserve evidence references where required.

PatientContext and EvaluatorContext must be separate types.

No universal context object may be shared between Patient Agent and Evaluator Agent.

API request and response schemas must not expose internal repository records directly.

## 17. Error Handling

Services must use explicit application-level errors.

The architecture should distinguish:

- Validation failure.
- Missing entity.
- Invalid state transition.
- Authorization failure.
- Idempotency conflict.
- Persistence failure.
- Model execution failure.
- Recovery-required condition.
- Unsupported schema or configuration.

API routes are responsible for translating service errors into appropriate HTTP responses.

Raw database exceptions and provider credentials must not be exposed to frontend users.

Errors must provide enough diagnostic information for local troubleshooting without leaking restricted information.

## 18. Dependency Injection

Services and repositories must receive their dependencies explicitly.

The architecture must avoid:

- Hidden global database connections.
- Import-time database initialization.
- Global mutable service instances.
- Circular service dependencies.
- Direct database access from API route handlers.
- Direct repository access from AI agent implementations.

A controlled application composition layer will construct the database manager, repositories, and services.

The exact dependency injection mechanism will be selected before implementation.

## 19. Testing Requirements

Each service must have isolated unit tests and persistence integration tests where applicable.

Tests must include:

- Successful operations.
- Invalid entity references.
- Cross-run reference rejection.
- Cross-session reference rejection.
- Invalid state transitions.
- Idempotent repetition.
- Conflicting idempotency keys.
- Transaction rollback.
- Failure during model execution.
- Preservation of therapist messages.
- Restricted context boundary enforcement.
- Evidence offset validation.
- Database integrity after failure.

Service tests must use temporary databases and must not modify real user databases.

## 20. Implementation Sequence

The proposed implementation sequence is:

1. CaseService.
2. RunService.
3. SessionService.
4. DisclosureService.
5. PatientContextService.
6. InteractionService.
7. EventProcessingService.
8. StateService.
9. MemoryService.
10. EvaluationService after its prerequisites are resolved.

The implementation order may be adjusted based on explicit dependency analysis.

Patient Agent integration must not begin before the required persistence and authorized-context boundaries are ready.

## 21. Acceptance Criteria

The Service Layer architecture will be considered ready for implementation when:

1. Every service has a defined responsibility.
2. Repository and service ownership boundaries are explicit.
3. Transaction ownership is explicit.
4. Cross-database validation responsibilities are explicit.
5. Patient and evaluator context boundaries are separate.
6. Model calls occur outside database write transactions.
7. Interaction idempotency and failure recovery are defined.
8. Evidence provenance is preserved.
9. Automatic state mutation remains disabled.
10. Memory lineage limitations are documented.
11. Evaluation prerequisites are explicitly recorded.
12. Service-level test expectations are documented.

## 22. Implementation Status

This document defines the planned Service Layer architecture.

The service classes described here are planned and must not be considered implemented merely because their contracts are documented.

Implementation must proceed incrementally, with tests and architecture review after each service.

<!-- CHARACTER_SERVICE_LAYER_NOTE_V0_1 -->
## Character model service responsibilities

The intended service layer reuses the existing case, disclosure,
PatientContext, memory, event, and state repositories.

New responsibilities are expected to include:

- Personality profile loading and immutable-version validation.
- Character-state snapshot initialization and retrieval.
- Evidence-aware state-transition validation.
- Memory proposal validation and controlled activation.
- Event proposal validation.
- Memory consolidation and contradiction handling.
- Assembly of the exact character version into PatientContext.

The LLM does not own persistence or canonical state. Orchestration services
coordinate model calls, validate proposals, and use short database
transactions. Model generation must occur outside an open SQLite transaction.

See `docs/CHARACTER_MODEL_SPEC.md`.
