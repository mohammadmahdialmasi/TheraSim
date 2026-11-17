# TheraSim — MVP Architecture Decisions

**Document Version:** 0.1
**Project Status:** Research Prototype / Pre-MVP
**Decision Status:** Initial Architecture Baseline
**Date:** 2026-11-14

---

## 1. Purpose

This document establishes the architectural decisions for the initial TheraSim MVP.

Its purpose is to resolve ambiguities and inconsistencies across the existing project specifications before implementation.

The decisions in this document take precedence over conflicting provisional implementation details in earlier architecture documents.

The project remains modular, local-first, extensible, and research-oriented.

These decisions may be revised through explicit, versioned architecture changes.

---

## 2. Product Scope

The initial MVP will provide an educational psychotherapy simulation environment based on Acceptance and Commitment Therapy (ACT).

### 2.1 Included Features

The initial target includes:

1. One fully fictional client: AVA-001.
2. Sequential psychotherapy sessions with no universal fixed count; AVA-001's
   three-session scenario is an example, not a required run length.
3. A Patient Agent for client simulation.
4. An Evaluator Agent for therapist feedback.
5. A structured Clinical State Engine.
6. A controlled disclosure mechanism.
7. Longitudinal session memory.
8. Session-level evaluation reports.
9. A final longitudinal evaluation report.
10. Evidence references to transcript messages.
11. Local language-model execution through Ollama.
12. Persian-first interaction.
13. Versioned prompts, rubrics, and simulation cases.
14. Automated software and behavioral tests.

### 2.2 Explicitly Excluded

The following are outside the initial MVP:

- Real-client records.
- Autonomous psychotherapy.
- Clinical diagnosis.
- Professional certification.
- Voice interaction.
- Video simulation.
- Multi-user collaboration.
- Cloud-based model execution.
- Distributed microservices.
- Multiple simultaneous synthetic clients.
- Fully automated clinical competency measurement.
- Claims of clinically validated simulation effectiveness.

---

## 3. Architectural Style

**Decision: Modular Monolith**

The initial backend will use a modular monolithic architecture.

All application services will run within one Python backend process, while language models will be accessed through the local Ollama runtime.

The backend will maintain explicit service and repository boundaries.

### 3.1 Reasoning

This approach provides:

- Simpler implementation.
- Lower resource consumption.
- Easier local debugging.
- Fewer deployment dependencies.
- Easier transactional database operations.
- Clear separation of component responsibilities.

The system will not initially use independently deployed microservices.

### 3.2 Initial Backend Modules

The proposed internal structure is:

- API Layer
- Orchestrator
- Patient Context Service
- Patient Agent
- Evaluator Agent
- Event Processing Service
- Clinical State Engine
- Memory Service
- Evaluation Service
- Model Provider
- Repository Layer
- Safety and Validation Layer

Logical separation does not imply separate operating-system processes.

Stronger process isolation may be introduced in later versions.

---

## 4. Agent Architecture

**Decision: Two primary LLM agents in the initial MVP.**

### 4.1 Patient Agent

Responsibilities:

- Simulate Ava.
- Preserve fictional identity.
- Respond naturally to therapist interactions.
- Follow controlled disclosure behavior.
- Use relevant longitudinal memory.
- Maintain behavioral consistency.
- Produce structured responses.

Input:

- Authorized patient context.
- Current simulation state.
- Relevant longitudinal memory.
- Recent transcript.
- Latest therapist message.

Output:

- PatientResponse.
- Optional candidate interaction annotations.

The Patient Agent cannot directly modify canonical clinical state.

### 4.2 Evaluator Agent

Responsibilities:

- Evaluate therapist behavior.
- Follow the applicable ACT rubric.
- Assess evidence from the transcript.
- Identify strengths and limitations.
- Reference supporting messages.
- Report insufficient evidence.
- Generate session-level and longitudinal reports.

Input:

- Authorized transcript.
- Versioned rubric.
- Applicable therapist-visible context.
- Evaluation scope.

The Evaluator Agent must never receive:

- Hidden clinical formulation.
- Undisclosed case information.
- Internal Patient Agent prompts.
- Future planned client responses.
- Restricted patient state.

### 4.3 Event Processing Service

**Decision: Event extraction will initially be implemented as an internal service, not an independently deployed LLM agent.**

Its initial responsibilities are:

- Record interaction events.
- Process session lifecycle events.
- Maintain transcript evidence references.
- Store structured candidate events.
- Support controlled memory updates.
- Prevent duplicate event processing.

The first implementation will prioritize deterministic event handling.

Model-assisted psychological event extraction may be introduced later behind the same service interface.

It must not directly modify canonical clinical state.

### 4.4 Memory Service

Memory processing will initially be handled by an internal backend service.

The MemoryExtractionAgent is an optional secondary model-assisted component,
not a primary conversational agent or a separate service process. It uses the
configured local provider only when available; the service remains the
authority for evidence validation, persistence, and review.

The initial implementation prioritizes structured memory records and transcript references. Model-generated proposals must remain inactive until evidence validation and explicit review; they must never be treated as authoritative summaries.

The MemoryExtractionAgent processes each successfully completed therapist/patient exchange through a durable, leased outbox. Its strict versioned output is saved for safe replay, and each proposal is validated against exact patient-authored transcript evidence before MemoryService stores it as `requires_review`. Empty output is valid. Explicit acceptance or rejection is required before a proposal can become active or terminally rejected. Revisions preserve lineage and supersede the prior active item only when the replacement is accepted. The sessions interface provides review controls; decisions are attributed to the authenticated single local reviewer account, which is not a multi-user authorization system.

---

## 5. Simulation Lifecycle

**Decision: A simulation run has no universal fixed session count. Sessions are created sequentially as needed and the user may complete the Run after the created sessions are complete.**

The lifecycle is:

1. Create simulation run.
2. Load the selected case version.
3. Create the initial state snapshot.
4. Create the first session.
5. Process therapist-patient interactions.
6. Record messages and interaction events.
7. Validate eligible state transitions.
8. Complete the session and finalize its transcript.
9. Generate a session evaluation when requested and supported.
10. Prepare validated longitudinal memory.
11. Add a subsequent session only after the previous session is complete.
12. Repeat the session workflow for as many sessions as the Run requires.
13. Complete the Run after at least one session exists and every created session is complete.

### 5.1 Session Ordering and Planning

Sessions are created incrementally and numbered sequentially from 1. There is no system-wide maximum; a specific versioned protocol may recommend or define its own planning policy.

The next session cannot begin before the prior session reaches an allowed completed state. The API does not permit callers to assign or change a session number.

### 5.2 Session Completion

Completing a session must finalize its transcript.

Evaluation generation is a separate operation.

An evaluation failure must never invalidate an already completed session.

---

## 6. Evaluation Architecture

**Decision: Two evaluation scopes are required.**

### 6.1 Session-Level Evaluation

Each completed session receives an independent evaluation report.

It assesses:

- Therapeutic relationship.
- Functional assessment.
- Psychological workability.
- Acceptance and willingness.
- Cognitive defusion.
- Present-moment awareness.
- Values clarification.
- Committed action.
- Clinical responsiveness.
- Safety and professional boundaries.

Each dimension must follow the applicable rubric.

Ratings:

- 0
- 1
- 2
- 3
- NE

NE must never be automatically converted to zero.

Each report must retain:

- Competency identifier.
- Rating.
- Justification.
- Supporting message references.
- Evidence excerpt or span.
- Alternative response where improvement is appropriate.
- Limitations.
- Confidence or uncertainty information.

No validated overall competency score will be calculated.

### 6.2 Longitudinal Evaluation

For a longitudinal evaluation, the Evaluator Agent receives the authorized finalized transcripts in the selected completed Run scope. The session count is not fixed.

`ACT_LONGITUDINAL_RUBRIC_V0` version 0.2 is count-agnostic; version 0.1 is retained as a historical three-session example. Both remain experimental. **Historical implementation status recorded for this document (2026-11-14):** The Evaluator Agent was not implemented, so longitudinal evaluation was unavailable at that time. This dated statement is superseded by the current implementation status in Section 21 and the current implementation baseline.

It will evaluate:

- Continuity of therapist behavior.
- Consistency of therapeutic formulation.
- Use of previous disclosures.
- Review of agreed exercises.
- Adaptation to client feedback.
- Changes in therapist interventions.
- Evidence of continuity or inconsistency.
- Appropriate revision of earlier hypotheses.

The evaluator must only use information that was available to the therapist during the simulation.

The longitudinal report must not assess the therapist against hidden client information.

### 6.3 Evaluation Restrictions

The Evaluator Agent must not:

- Reward technique counts.
- Assume patient improvement demonstrates therapist competence.
- Penalize the therapist for not discovering undisclosed information without a reasonable opportunity.
- Invent evidence.
- Diagnose the synthetic client.
- Claim professional certification or validated clinical competence.

---

## 7. Case Information and Disclosure

**Decision: Case information will be divided into explicit information items.**

Each synthetic case will contain identifiable information records.

Example identifiers for AVA-001:

- AVA-FACT-001
- AVA-FACT-002
- AVA-FACT-003
- AVA-FACT-004

Each record should define:

- Information item identifier.
- Case version.
- Information classification.
- Disclosure policy.
- Related case formulation section.
- Relevant evidence references, when disclosed.
- Disclosure status.

### 7.1 Disclosure Status

Initial statuses:

- not_disclosed
- candidate_disclosed
- confirmed_disclosed
- requires_review

The disclosure system must not treat the four authored disclosure levels as mandatory sequential stages.

They are contextual guidance rather than fixed steps of treatment.

### 7.2 Patient Context

The Patient Context Service retrieves the information required by the Patient Agent.

It must consider:

- Information already disclosed.
- Information potentially appropriate for disclosure.
- Current conversational context.
- The fictional client's disclosure readiness.
- Relevant previous interactions.

### 7.3 Disclosure Tracking

The Patient Agent may propose disclosure annotations referencing case fact identifiers and supporting response text.

These annotations are candidates, not authoritative records.

The backend must validate the referenced case facts and message evidence before updating disclosure records.

Ambiguous disclosure must remain a candidate or require review.

The application must not claim perfect semantic verification based only on keyword matching.

---

## 8. Clinical State Engine

**Decision: The Clinical State Engine remains deterministic and application-controlled.**

The initial six variables are:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Each variable uses the initial simulation range of 0–4.

These variables are simulation parameters, not validated psychological measurements.

### 8.1 Initial State

The initial AVA-001 values remain unchanged from the approved case specification:

| Variable | Initial Value |
|---|---:|
| Therapeutic alliance | 2 |
| Disclosure readiness | 1 |
| Experiential avoidance | 4 |
| Willingness | 1 |
| Values clarity | 2 |
| Committed action readiness | 1 |

### 8.2 Transition Policy

A therapist intervention alone cannot modify a state variable.

A proposed transition requires:

- Relevant interaction evidence.
- A patient response or other appropriate contextual evidence.
- An applicable transition rule.
- Validated references.
- Range and consistency checks.

### 8.3 Initial Implementation Restriction

Before each variable has operational behavioral anchors and reviewed transition rules, the system must not automatically change its value based on unrestricted LLM interpretation.

Uncertain transitions remain unchanged or require review.

The initial MVP must support state storage, historical snapshots, candidate transitions, and deterministic validation.

More advanced adaptive state modeling is deferred.

---

## 9. Longitudinal Memory

**Decision: Structured memory is the source of continuity.**

The transcript remains the original record of the interaction.

Memory stores selected information with references to the original messages.

### 9.1 Initial Memory Categories

- disclosed_facts
- relevant_client_experiences
- therapist_interventions
- agreed_homework
- reported_homework_outcomes
- unresolved_topics
- relevant_interaction_patterns
- accepted_state_transitions

### 9.2 Information Classification

Each memory record must distinguish:

- Confirmed fictional facts.
- Explicit patient disclosures.
- Therapist hypotheses.
- System-generated summaries.
- Reported outcomes.
- Structured observations.

These categories must never be merged into one unqualified free-text summary.

### 9.3 Memory Generation

The initial implementation will prioritize explicit structured records and deterministic memory selection.

Optional language-model summaries may be introduced later.

Every memory item must preserve its originating message references and classification.

---

## 10. Event Processing

**Decision: Event processing will be conservative.**

The initial implementation will distinguish:

### A. Deterministic Events

Examples:

- session_started
- therapist_message_received
- patient_response_generated
- session_completed
- evaluation_generated
- model_execution_failed

These events can be created from application operations.

### B. Candidate Behavioral Events

Examples:

- emotional_experience_disclosed
- homework_agreed
- intervention_declined
- willingness_expressed
- values_clarification_observed
- cognitive_defusion_response_observed

These may require language-model assistance or review.

They must remain candidates until validated.

### 10.1 No Automatic Clinical Interpretation

The event processing layer must not infer a confirmed psychological change from a single ambiguous statement.

An extracted event does not automatically produce a state transition.

---

## 11. Database Decisions

**Decision: Two SQLite database files will be used for the initial local prototype.**

### 11.1 Operational Database

`therasim.db`

Stores:

- Case metadata.
- Simulation runs.
- Sessions.
- Messages.
- Events.
- Event evidence.
- State snapshots.
- State transitions.
- Longitudinal memory.
- Rubric versions.
- Evaluation reports.
- Model execution records.
- Audit events.
- Disclosure tracking metadata.

### 11.2 Restricted Case Database

`case_vault.db`

Stores:

- Restricted case formulations.
- Undisclosed personal history.
- Hidden case-specific information.
- Disclosure policies.
- Restricted simulation instructions.

### 11.3 Security Interpretation

Separate SQLite files provide logical data separation, not complete operating-system security.

The initial implementation is a local single-user prototype.

The Patient Context Service is the authorized access path to restricted case data.

The Evaluator Agent must receive explicitly constructed input objects and must not receive a connection or unrestricted repository to the restricted database.

---

## 12. Database Schema Amendments Required

Before executable database implementation, the following additions must be incorporated into the provisional schema.

### 12.1 Evaluation Scope

The evaluations table must support:

- session-level evaluation.
- run-level longitudinal evaluation.

Required additions:

- evaluation_scope
- run_id
- nullable session_id where permitted.

A run-level evaluation references the complete simulation run rather than a single session.

### 12.2 Case Fact Registry

Introduce a structured registry for individual case information items.

Proposed table:

`case_facts`

### 12.3 Case Fact Disclosures

Introduce a disclosure history table.

Proposed table:

`case_fact_disclosures`

It must link information items to their disclosure candidates or confirmed evidence messages.

### 12.4 Interaction Idempotency

Introduce a record for message submission operations.

Proposed table:

`interaction_requests`

It should store:

- request_id
- session_id
- idempotency_key
- request_hash
- therapist_message_id
- patient_message_id
- processing_status
- error_code
- created_at
- completed_at

The combination of session ID and idempotency key must be unique.

### 12.5 Evaluation Evidence

Evaluation records must support:

- Supporting message identifiers.
- Evidence excerpts or character spans.
- Competency-specific justifications.
- Alternative responses.
- Uncertainty and limitations.

These additions must be reflected in the Pydantic contracts and database migrations.

---

## 13. API Decisions

**Decision: Versioned REST API using FastAPI.**

The initial interaction workflow will use synchronous HTTP requests.

Streaming and background task infrastructure are deferred.

### 13.1 External Endpoints

The current external endpoint structure is retained with the following additions or clarifications:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health |
| GET | `/api/v1/cases` | List available cases |
| POST | `/api/v1/simulation-runs` | Create simulation run |
| GET | `/api/v1/simulation-runs/{run_id}` | Retrieve run |
| POST | `/api/v1/simulation-runs/{run_id}/sessions` | Create sequential session |
| POST | `/api/v1/sessions/{session_id}/messages` | Submit therapist message |
| GET | `/api/v1/sessions/{session_id}/messages` | Retrieve transcript |
| POST | `/api/v1/sessions/{session_id}/complete` | Complete session |
| POST | `/api/v1/sessions/{session_id}/evaluations` | Generate session evaluation |
| GET | `/api/v1/evaluations/{evaluation_id}` | Retrieve evaluation |
| POST | `/api/v1/simulation-runs/{run_id}/evaluations` | Generate longitudinal evaluation |

### 13.2 Idempotency

Message submission must support idempotency keys.

A repeated request with the same key and identical payload must not create a duplicate interaction.

Reusing the same key with a different payload must produce a conflict response.

### 13.3 Concurrency

The initial MVP allows only one active message-generation operation per session.

Concurrent requests must not corrupt message ordering or duplicate state transitions.

### 13.4 Error Handling

Patient generation failure must not delete the already persisted therapist message.

Evaluation failure must not invalidate a completed session.

All failure states must be recorded and recoverable.

---

## 14. Model Runtime Decisions

**Decision: Ollama is the initial local model provider.**

### 14.1 Initial Runtime

- Python backend.
- FastAPI.
- Pydantic.
- SQLite.
- Ollama.
- React frontend.
- Pytest.
- Git.

### 14.2 Model Assignment

Model identifiers must be configurable independently for Patient Agent and Evaluator Agent.

However, the initial implementation may use one compatible local model sequentially for both components.

Parallel model execution is not required.

Event extraction and memory processing must not require additional simultaneously loaded models.

### 14.3 Model Selection

Specific model selection will occur after a controlled compatibility and performance test.

No model will be considered suitable solely because it produces fluent Persian responses.

It must also be assessed for:

- Instruction adherence.
- Structured output validity.
- Behavioral consistency.
- Disclosure control.
- Evidence grounding.
- Resource consumption.

---

## 15. Language Decisions

**Decision: Persian-first implementation.**

The first working vertical slice will support Persian end-to-end.

The data contracts must retain language fields and support future localization.

English localization will be added after the Persian workflow is stable.

Language must be kept separate from therapeutic modality and case identity.

The system must not assume that literal translation guarantees equivalent psychological meaning.

---

## 16. Security Decisions

The initial application is intended for local single-user use.

Mandatory requirements:

1. Bind FastAPI to localhost by default.
2. Keep database files outside public frontend directories.
3. Prevent the frontend from accessing restricted storage.
4. Keep Patient and Evaluator prompts separate.
5. Do not expose internal agent reasoning.
6. Validate model inputs and outputs.
7. Prevent direct model modification of canonical clinical state.
8. Restrict agent tools.
9. Avoid logging restricted case content and secrets.
10. Treat therapist messages as untrusted conversational input.

Prompt instructions must not be treated as a substitute for application-level access control.

---

## 17. Test and Benchmark Decisions

The Test Strategy remains the primary testing specification.

Initial test priorities:

1. Session lifecycle correctness.
2. Agent input and output schema compliance.
3. Patient identity consistency.
4. Disclosure policy behavior.
5. Longitudinal continuity.
6. State transition integrity.
7. Evaluator evidence grounding.
8. Information leakage prevention.
9. Persian language quality.
10. Local model performance.

Human expert review is required before making claims about clinical validity or educational effectiveness.

The initial benchmark will not claim population-level generalizability from a single synthetic case.

---

## 18. Implementation Order

The following sequence is approved for the initial development process.

### Phase 1 — Contract Finalization

- Update Data Contracts.
- Amend Database Schema.
- Amend API Contracts.
- Define missing case disclosure structures.
- Finalize implementation-oriented status and lifecycle values.

### Phase 2 — Python Project Foundation

- Establish Python project structure.
- Configure virtual environment.
- Configure dependency management.
- Add Pydantic schemas.
- Configure Pytest.
- Implement configuration loading.

### Phase 3 — Persistence Layer

- Implement SQLite connections.
- Implement database migrations.
- Implement repositories.
- Add foreign-key and transaction tests.
- Add operational and restricted database access interfaces.

### Phase 4 — Core Simulation

- Implement Orchestrator.
- Implement Session Service.
- Implement Patient Context Service.
- Integrate Ollama.
- Implement Patient Agent.
- Validate and persist responses.

### Phase 5 — State and Memory

- Implement Event Processing Service.
- Implement Clinical State Engine.
- Implement state snapshots.
- Implement disclosure tracking.
- Implement structured longitudinal memory.

### Phase 6 — Evaluation

- Implement Evaluator Agent.
- Integrate ACT rubric.
- Implement evidence validation.
- Generate session-level reports.
- Generate run-level longitudinal reports.

### Phase 7 — API and Frontend

- Implement external REST endpoints.
- Implement Therapist Interface.
- Connect session workflow.
- Present evaluation reports.

### Phase 8 — Validation

- Run automated tests.
- Conduct behavioral testing.
- Conduct security testing.
- Compare local models.
- Record known limitations.

---

## 19. Deferred Architecture

The following features are deliberately deferred:

- Independently deployed microservices.
- Third-party cloud model providers.
- Voice and video simulation.
- Multi-user collaboration.
- Complex learned state-transition policies.
- Fully automated semantic disclosure verification.
- Advanced prompt optimization.
- Automatic clinical competency scoring.
- Large-scale population benchmarks.
- Real-client data support.

Deferred functionality must not be assumed to exist in the MVP.

---

## 20. Architecture Change Management

Every significant architectural change must be documented.

A decision record should contain:

- decision_id
- decision_title
- date
- status
- context
- selected_decision
- alternatives_considered
- consequences
- affected_documents

Changes that affect data contracts, APIs, schemas, security boundaries, or benchmark interpretation must trigger review of the relevant documents.

Existing historical specifications must not be silently overwritten without version control.

---

## 21. Final MVP Definition

**Historical implementation status recorded for this document (2026-11-14):**
At that time, the Evaluator Agent and session/longitudinal assessment were not
implemented, and evaluation-generation requests were unavailable rather than
returning fabricated completed reports. Event extraction, state transitions,
localization, analytics, and multi-modality execution were also incomplete.
These statements preserve the status recorded when this decision document was
written; they are not current implementation claims.

**Current implementation clarification — 2026-11-17:** ACT remains the only
runnable modality. Experimental local-model-backed ACT session and longitudinal
evaluators exist, but semantic evidence validity and clinical/psychometric
validity are unestablished. Authenticated append-only human evaluation reviews
exist. Raw competency observations retain rubric version/hash, confidence,
evidence references, and missing-data reasons. Run analytics provide persisted
data-based descriptive summaries, exploratory raw-rating-code charts, and JSON
export; these are not validated competency trends or clinical outcomes.
Treatment-plan revisions are human-supervised and limited to available
evidence; autonomous clinical treatment adaptation is not implemented.

TheraSim is not a validated clinical competency instrument, diagnostic system,
treatment service, or replacement for human supervision.

---

**End of Document**

<!-- CHARACTER_MVP_DECISION_NOTE_V0_1 -->
## Character-centered simulation priority

The MVP character model must demonstrate stable identity and independent
longitudinal trajectories before expanding the number of therapeutic
approaches or synthetic cases.

The initial implementation priority is one carefully authored character
profile with explicit uncertainty, run-isolated state, and evidence-linked
memory. AVA-001 is the initial authoring example, not a validated
representation of a psychological population.

A reusable character architecture takes priority over hard-coding
characteristics into Patient Agent prompts.

See `CHARACTER_MODEL_SPEC.md` and ADR-0004.
