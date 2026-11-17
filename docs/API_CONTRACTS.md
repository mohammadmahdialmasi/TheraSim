# TheraSim — API Contracts

**Document Version:** 0.4
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-17
**Architecture Reference:** MVP_DECISIONS.md
**Data Contract Reference:** DATA_CONTRACTS.md
**Database Reference:** DATABASE_SCHEMA.md
**Security Reference:** SECURITY_BOUNDARIES.md

---

## 1. Purpose

This document defines the external API and internal service contracts for the initial TheraSim MVP.

It establishes communication rules between:

- Therapist Interface.
- FastAPI backend.
- Orchestrator.
- Patient Context Service.
- Patient Agent.
- Event Processing Service.
- Clinical State Engine.
- Memory Service.
- Evaluation Service.
- Evaluator Agent.
- Repository Layer.

The API architecture must ensure:

- Consistent communication.
- Sequential simulation lifecycle management.
- Session-level and longitudinal evaluations.
- Idempotent therapist interactions.
- Controlled access to synthetic case information.
- Structured error handling.
- Evidence-linked evaluation reports.
- Reproducible operations.
- Compatibility with local language-model execution.

The MVP uses a modular monolithic backend.

Internal service contracts do not automatically require independent HTTP endpoints.

MVP architectural decisions take precedence over earlier provisional specifications.

**Implementation status:** These sections describe intended contracts and must
not be read as proof that an Evaluator Agent exists. Evaluation persistence,
rubrics, and read routes are present, but evaluation generation currently
returns HTTP 503 with `evaluator_unavailable_experimental` and creates no
report. Historical records with no Evaluator Agent model-run identifier are
returned with `status: experimental`; stored placeholder items and evidence
are withheld. The current count-agnostic longitudinal rubric is version 0.2.

---

## 2. API Architecture

### 2.1 Backend-Mediated Communication

The frontend communicates only with the FastAPI backend.

The backend coordinates all simulation components through explicit service interfaces.

The frontend must not communicate directly with:

- Ollama.
- Patient Agent internals.
- Evaluator Agent internals.
- SQLite databases.
- Restricted case storage.
- Clinical State Engine internals.
- Memory Service internals.

### 2.2 Communication Flow

The normal interaction workflow is:

1. Frontend submits a therapist message.
2. API validates the request.
3. Orchestrator validates the session.
4. InteractionRequest is created or retrieved.
5. Therapist message is persisted.
6. Patient Context Service constructs authorized PatientContext.
7. Patient Agent generates a response.
8. Backend validates the response.
9. Patient response is persisted.
10. Deterministic interaction events are recorded.
11. API returns the validated interaction result.

Behavioral event extraction and state transition validation may run as subsequent internal processing operations.

A failed optional event extraction operation must not invalidate a successfully persisted therapist-patient interaction.

### 2.3 API Categories

The architecture defines two communication categories.

**A. External REST API**

Endpoints accessible to the Therapist Interface.

**B. Internal Service Contracts**

Interfaces used by the Orchestrator and internal components.

Internal contracts must remain separate from public HTTP request models.

---

## 3. API Conventions

### 3.1 Base URL

Initial local development:

`http://127.0.0.1:8000`

### 3.2 API Versioning

All application endpoints use:

`/api/v1`

Example:

`/api/v1/sessions`

Breaking changes must be introduced through an explicitly managed API version or compatibility migration.

### 3.3 HTTP Methods

| Method | Purpose |
|---|---|
| GET | Retrieve resources |
| POST | Create resources or execute operations |
| PATCH | Modify permitted resource attributes |
| DELETE | Delete resources when explicitly authorized |

The initial MVP primarily uses GET and POST.

Completed transcripts and historical state records must not be silently overwritten or deleted.

### 3.4 Content Type

Default request and response content type:

`application/json`

### 3.5 Identifiers

Resource identifiers use UUID strings unless another identifier format is explicitly defined.

### 3.6 Timestamps

All timestamps use UTC and ISO 8601 representation with timezone information.

Example:

`2026-11-14T12:30:00Z`

### 3.7 Pagination

Collection endpoints may support:

- limit
- offset

The backend must enforce a maximum page size.

### 3.8 Request Correlation

Each request should receive a unique request identifier.

The identifier must be included in:

- Application logs.
- Structured error responses.
- Relevant audit records.

It must not contain sensitive case information.

---

## 4. Standard Response Structures

### 4.1 Successful Single Resource Response

Example:

```json
{
  "data": {
    "session_id": "uuid",
    "status": "active"
  }
}
```

### 4.2 Collection Response

Example:

```json
{
  "data": [],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 0
  }
}
```

### 4.3 Error Response

All API errors must use the following structure:

```json
{
  "error": {
    "code": "SESSION_NOT_ACTIVE",
    "message": "The requested session is not active.",
    "details": {},
    "request_id": "uuid"
  }
}
```

The `code` field must remain stable for frontend error handling.

The `message` field must be understandable to the user or developer.

Internal stack traces, restricted case information, hidden prompts, and model context must never appear in external errors.

### 4.4 Successful Operation Metadata

Operations that may be retried should expose relevant identifiers and status information.

For example:

- request_id
- operation_status
- session_id
- created_at

---

# PART I — CASE AND SIMULATION MANAGEMENT

## 5. Health Check

### Endpoint

`GET /health`

Purpose:

Verify basic backend availability.

Example response:

```json
{
  "data": {
    "status": "ok",
    "application": "TheraSim"
  }
}
```

The health endpoint must not expose:

- Database records.
- Model prompts.
- Secrets.
- Restricted case information.
- Internal filesystem paths.

Detailed infrastructure diagnostics are outside the public health response.

---

## 6. Case Management

### 6.1 List Available Cases

**Endpoint:**

`GET /api/v1/cases`

Purpose:

Retrieve synthetic cases available for simulation.

Query parameters:

- limit
- offset
- modality
- language

Response:

```json
{
  "data": [
    {
      "case_id": "uuid",
      "case_code": "AVA-001",
      "display_name": "Ava",
      "modality": "ACT",
      "available_languages": ["fa", "en"],
      "status": "active"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 1
  }
}
```

Only approved case metadata may be returned.

The endpoint must not include:

- Hidden clinical formulation.
- Undisclosed personal history.
- Restricted case facts.
- Patient Agent instructions.
- Internal disclosure policies.

### 6.2 Retrieve Case Information

**Endpoint:**

`GET /api/v1/cases/{case_id}`

Purpose:

Retrieve authorized therapist-facing case information.

The response may include:

- case_id
- case_code
- display_name
- modality
- available_languages
- approved presentation information
- active case version

The response must include only information explicitly authorized for therapist visibility.

The public case profile must not expose the complete CaseDefinition.

---

## 7. Simulation Run Management

### 7.1 Create Simulation Run

**Endpoint:**

`POST /api/v1/simulation-runs`

Purpose:

Create a longitudinal simulation run.

Request:

```json
{
  "case_id": "uuid",
  "case_version_id": "uuid",
  "modality": "ACT",
  "language": "fa",
  "protocol_id": "ACT_EDUCATIONAL_SIMULATION",
  "protocol_version": "0.1",
  "session_planning_policy": "flexible",
  "evaluation_rubric_id": "ACT_RUBRIC_V0",
  "evaluation_rubric_version": "0.2"
}
```

Required fields:

- case_id
- modality
- language
- session_planning_policy

The case_version_id may be omitted when the backend can identify the approved active version.
Protocol and rubric fields default to the currently supported ACT configuration.
Supported planning policies are `flexible`, `goal_based`, `milestone_based`,
and `open_ended`; none sets a universal session count.

The backend must verify:

- Case existence.
- Case availability.
- Case version compatibility.
- Supported therapeutic modality.
- Supported language.
- Supported protocol and rubric versions.
- Planning policy compatibility with the selected protocol.

Response:

```json
{
  "data": {
    "run_id": "uuid",
    "case_id": "uuid",
    "case_version_id": "uuid",
    "modality": "ACT",
    "language": "fa",
    "status": "initialized",
    "protocol_id": "ACT_EDUCATIONAL_SIMULATION",
    "protocol_version": "0.1",
    "session_planning_policy": "flexible",
    "evaluation_rubric_id": "ACT_RUBRIC_V0",
    "evaluation_rubric_version": "0.2",
    "created_at": "2026-11-14T12:30:00Z"
  }
}
```

A simulation run must retain its original case version throughout its execution.

### 7.2 Retrieve Simulation Run

**Endpoint:**

`GET /api/v1/simulation-runs/{run_id}`

Purpose:

Retrieve authorized simulation metadata.

Response fields:

- run_id
- case_id
- case_version_id
- modality
- language
- status
- session_count
- protocol_id
- protocol_version
- session_planning_policy
- evaluation_rubric_id
- evaluation_rubric_version
- started_at
- completed_at
- created_at

Restricted patient state and hidden case information must not be exposed.

### 7.3 List Simulation Runs

**Endpoint:**

`GET /api/v1/simulation-runs`

Purpose:

List persisted simulation runs so the local workspace can restore
an existing run after navigation or browser refresh.

Query parameters:

- `limit`: optional, default 20, range 1 to 100.
- `offset`: optional, default 0, minimum 0.
- `status`: optional run status filter.

The response contains the standard authorized run metadata for each
result. Restricted case information and hidden patient state must
not be included.

### 7.4 Simulation Run Lifecycle

The following endpoints expose the supported run lifecycle actions.
Each endpoint returns the standard run response defined in Section 7.2.

**Start a run**

`POST /api/v1/simulation-runs/{run_id}/start`

Allowed transition: `initialized` to `active`.

**Interrupt a run**

`POST /api/v1/simulation-runs/{run_id}/interrupt`

Allowed transition: `active` to `interrupted`.

**Resume a run**

`POST /api/v1/simulation-runs/{run_id}/resume`

Allowed transition: `interrupted` to `active`.

**Complete a run**

`POST /api/v1/simulation-runs/{run_id}/complete`

Allowed transition: `active` to `completed`.

The backend must verify that at least one session exists, session numbers
are sequential, and all created sessions have status `completed` before
completing the run. Otherwise, the endpoint returns HTTP 409.

All lifecycle actions return HTTP 404 when the run does not exist and
HTTP 409 when the requested transition is not permitted.

Run failure is system-managed. The application service operation
`fail_run` is not exposed as a therapist-facing endpoint.

### 7.5 List Simulation Sessions

**Endpoint:**

`GET /api/v1/simulation-runs/{run_id}/sessions`

Purpose:

Retrieve sessions belonging to a simulation run.

Response fields:

- session_id
- session_number
- status
- started_at
- ended_at

Sessions must be returned in chronological order.

---

# PART II — SESSION MANAGEMENT

## 8. Create Session

### Endpoint

`POST /api/v1/simulation-runs/{run_id}/sessions`

Purpose:

Create the next permitted session in the simulation run.

### 8.1 Request

The client must not select an arbitrary session number.

The Orchestrator determines the next session number.

Initial request body:

```json
{}
```

### 8.2 Validation Rules

The backend must verify:

- The simulation run exists.
- The run is not completed or failed.
- The previous session, if any, has been completed.
- Previous sessions have reached an allowed completed state.
- The requested case version remains available.
- Required longitudinal context can be constructed.

Session numbering must be assigned by the backend:

Session numbering begins at 1 and increments by one without a universal upper limit.

The API does not support arbitrary session insertion or session-number modification.

### 8.3 Response

```json
{
  "data": {
    "session_id": "uuid",
    "run_id": "uuid",
    "session_number": 1,
    "status": "active",
    "started_at": "2026-11-14T12:30:00Z"
  }
}
```

### 8.4 Conflict Handling

A request to create Session 2 before Session 1 is completed must be rejected.

An existing active session must not be duplicated.

---

## 9. Retrieve Session

### Endpoint

`GET /api/v1/sessions/{session_id}`

Purpose:

Retrieve authorized session metadata.

Response fields:

- session_id
- run_id
- session_number
- status
- started_at
- ended_at
- transcript_version

The response must not expose:

- Hidden PatientContext.
- Internal agent state.
- Restricted clinical formulation.
- Private memory records.
- Internal model reasoning.

---

## 10. Retrieve Session Messages

### Endpoint

`GET /api/v1/sessions/{session_id}/messages`

Purpose:

Retrieve the therapist-visible session transcript.

Query parameters:

- limit
- offset

Response example:

```json
{
  "data": [
    {
      "message_id": "uuid",
      "sequence_number": 1,
      "role": "therapist",
      "content": "Can you tell me more about that experience?",
      "created_at": "2026-11-14T12:31:00Z"
    },
    {
      "message_id": "uuid",
      "sequence_number": 2,
      "role": "patient",
      "content": "I remember feeling uncomfortable when my colleague interrupted me.",
      "created_at": "2026-11-14T12:31:05Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 2
  }
}
```

Only authorized therapist-visible messages may be returned.

Internal reasoning and hidden prompts must not be included.

---

# PART III — THERAPIST INTERACTION

## 11. Submit Therapist Message

### Endpoint

`POST /api/v1/sessions/{session_id}/messages`

Purpose:

Submit a therapist message and receive a synthetic client response.

### 11.1 Request

Required header:

`Idempotency-Key: unique-operation-key`

Request body:

```json
{
  "content": "Can you describe what happened during that meeting?"
}
```

Required field:

- content

The original message content must be preserved.

The backend must validate:

- Session existence.
- Active session status.
- Message length.
- Message format.
- Idempotency key.
- Request payload hash.

### 11.2 Processing Sequence

1. Validate the session.
2. Validate the idempotency key.
3. Calculate the request hash.
4. Check for an existing InteractionRequest.
5. Return the existing result when the operation has already completed.
6. Return processing status if the operation is still active.
7. Create a new InteractionRequest when appropriate.
8. Persist the therapist message exactly once.
9. Construct PatientContext.
10. Invoke Patient Agent.
11. Validate the PatientResponse.
12. Persist the patient response.
13. Record factual, evidence-linked application events for the therapist message and patient response.
14. Complete the InteractionRequest.
15. Return the interaction result.

The messages, their factual application events, event evidence, and completed request status are committed atomically. These events record only that the messages occurred; they are not clinical interpretations or validated psychological changes. Behavioral event extraction is a separate future processing step and must not rewrite or invalidate the persisted interaction.

### 11.3 Successful Response

HTTP status: `201 Created`

Example:

```json
{
  "data": {
    "request_id": "uuid",
    "operation_status": "completed",
    "therapist_message": {
      "message_id": "uuid",
      "sequence_number": 1,
      "role": "therapist",
      "content": "Can you describe what happened during that meeting?"
    },
    "patient_response": {
      "message_id": "uuid",
      "sequence_number": 2,
      "role": "patient",
      "content": "I remember feeling embarrassed when my colleague interrupted me."
    },
    "session_status": "active"
  }
}
```

### 11.4 Idempotency Rules

The combination of session_id and Idempotency-Key must be unique.

When the same key and identical payload are submitted again:

- No duplicate therapist message may be created.
- No duplicate persisted patient response may be created.
- The existing operation status or result must be returned.

When the same key is reused with a different payload:

- The API must return an idempotency conflict.

A completed request replay may return HTTP `200 OK` with the original result.

A request already being processed may return HTTP `202 Accepted` with its request identifier and current status.

### 11.5 Model Failure

If Patient Agent generation fails after the therapist message has been persisted:

- Preserve the therapist message.
- Keep the InteractionRequest record.
- Mark the operation as failed.
- Record the model execution failure.
- Do not fabricate a patient response.
- Do not automatically modify clinical state.

A retry using the original idempotency key may resume the failed operation after recovery checks.

The backend must first verify whether a patient response has already been persisted.

### 11.6 Recovery and Exactly-Once Limitations

The API guarantees that repeated requests with the same idempotency key do not create duplicate persisted interaction effects.

It does not guarantee that the local language model will be invoked exactly once after every possible process crash.

If the process fails after model generation but before response persistence, a later recovery may require another generation.

The resulting operation must still preserve a single authoritative persisted interaction result.

This limitation must remain explicit.

---

## 12. Retrieve Interaction Request Status

### Endpoint

`GET /api/v1/interaction-requests/{request_id}`

Purpose:

Retrieve the processing status of a previously submitted therapist message operation.

Response:

```json
{
  "data": {
    "request_id": "uuid",
    "session_id": "uuid",
    "processing_status": "failed",
    "therapist_message_id": "uuid",
    "patient_message_id": null,
    "error_code": "MODEL_EXECUTION_FAILED",
    "created_at": "2026-11-14T12:31:00Z",
    "completed_at": null
  }
}
```

This endpoint must return operational metadata only.

The public processing states are `in_progress`, `completed`, and `failed`.

The response must not expose idempotency keys, request hashes, attempt tokens,
lease timestamps, or internal model-run identifiers.

A client may poll this endpoint while an operation is `in_progress`.
When an operation is `failed`, recovery must replay the original POST using
the same idempotency key and identical therapist message content. A new key
would represent a new therapist turn and must not be used for recovery.

It must not expose:

- Restricted PatientContext.
- Internal prompts.
- Hidden case information.
- Unfiltered model output.
- Application secrets.

The request status must distinguish:

- in_progress
- completed
- failed

---

# PART IV — SESSION COMPLETION

## 13. Complete Session

### Endpoint

`POST /api/v1/sessions/{session_id}/complete`

Purpose:

Complete an active simulation session.

### 13.1 Request

```json
{
  "completion_reason": "normal"
}
```

Allowed completion reasons:

- normal
- trainee_ended
- system_interrupted

### 13.2 Processing Requirements

The backend must:

1. Validate the session.
2. Verify that no message operation is still active.
3. Finalize all persisted interaction records.
4. Finalize the transcript version.
5. Calculate and persist its content hash.
6. Record the completion timestamp.
7. Update the session status.
8. Record the completion audit event.

### 13.3 Response

```json
{
  "data": {
    "session_id": "uuid",
    "status": "completed",
    "transcript_version": 1,
    "ended_at": "2026-11-14T13:00:00Z"
  }
}
```

### 13.4 Idempotency

Repeated completion requests for an already completed session must return the existing completion result without modifying the transcript.

An interrupted or failed session must not be represented as successfully completed.

### 13.5 Evaluation Separation

Session completion and evaluation generation are independent operations.

A failed evaluation must not change a completed session back to an active state.

---

# PART V — EVALUATION API

## 14. Session-Level Evaluation

### Endpoint

`POST /api/v1/sessions/{session_id}/evaluations`

Purpose:

Generate a formative evaluation report for one completed session.

### 14.1 Request

```json
{
  "rubric_id": "ACT_RUBRIC_V0",
  "rubric_version": "0.2"
}
```

Required fields:

- rubric_id
- rubric_version

### 14.2 Preconditions

The backend must verify:

- Session exists.
- Session belongs to a valid simulation run.
- Session status is completed.
- Transcript has been finalized.
- Requested rubric exists.
- Rubric is compatible with the session modality.
- Transcript version is available.

### 14.3 Evaluator Input

The Evaluation Service constructs an explicit EvaluationInput object.

The Evaluator Agent receives:

- Finalized session transcript.
- Exact transcript version.
- Authorized therapist-visible context.
- Applicable rubric.
- Evaluation instructions.

It must not receive:

- Restricted clinical formulation.
- Hidden CaseFact records.
- Undisclosed personal history.
- Patient Agent internal prompts.
- Private simulation state.
- Future planned responses.

### 14.4 Response

HTTP status: `201 Created`

```json
{
  "data": {
    "evaluation_id": "uuid",
    "evaluation_scope": "session",
    "session_id": "uuid",
    "run_id": "uuid",
    "status": "completed",
    "rubric_id": "ACT_RUBRIC_V0",
    "rubric_version": "0.2",
    "created_at": "2026-11-14T13:05:00Z"
  }
}
```

### 14.5 Duplicate Evaluation Handling

The initial MVP should maintain one canonical completed evaluation for each:

- Session.
- Transcript version.
- Rubric version.
- Evaluation scope.

A repeated request using the same evaluation configuration must return the existing report instead of generating an unintended duplicate.

Explicit evaluation revision management is deferred.

### 14.6 Failure Handling

If evaluation generation fails:

- Preserve the completed transcript.
- Record the failed model execution.
- Mark the evaluation operation as failed.
- Do not return an incomplete report as completed.
- Allow a controlled retry.

---

## 15. Retrieve Session Evaluations

### Endpoint

`GET /api/v1/sessions/{session_id}/evaluations`

Purpose:

List evaluations associated with a session.

Response fields:

- evaluation_id
- evaluation_scope
- rubric_id
- rubric_version
- status
- created_at

The API may return multiple records when historical revisions are supported in future versions.

---

## 16. Generate Longitudinal Evaluation

### Endpoint

`POST /api/v1/simulation-runs/{run_id}/evaluations`

Purpose:

Generate a longitudinal evaluation across the explicitly selected completed session scope.

This is a required capability of the initial MVP.

### 16.1 Request

```json
{
  "rubric_id": "ACT_LONGITUDINAL_RUBRIC_V0",
  "rubric_version": "0.2"
}
```

Required fields:

- rubric_id
- rubric_version

The longitudinal rubric may share competency definitions with the session-level ACT rubric but must explicitly define longitudinal evaluation criteria.

### 16.2 Preconditions

The backend must verify:

1. The simulation run exists.
2. The run uses the expected case version.
3. At least one session exists and every created session is completed.
4. Every included transcript is finalized.
5. Session ordering is valid.
6. No transcript included in the requested evaluation scope is missing.
7. The requested longitudinal rubric exists.
8. The rubric is compatible with the simulation modality.

Longitudinal evaluation must not run on incomplete simulations.

### 16.3 Evaluator Input

The Evaluation Service constructs one LongitudinalEvaluationInput.

It contains:

- run_id
- case_version_id
- modality
- language
- rubric identifier and version
- the finalized transcripts included in the selected evaluation scope
- transcript versions
- transcript hashes
- therapist-visible context by session
- longitudinal evaluation instructions

Transcripts must be presented in chronological order.

The evaluator must not receive:

- RestrictedCaseContext.
- Undisclosed personal history.
- Hidden case fact definitions.
- Internal Patient Agent instructions.
- Private state variables.
- Unvalidated candidate events.

The Evaluator Agent must assess only information legitimately available to the therapist during the simulation.

### 16.4 Longitudinal Evaluation Dimensions

The longitudinal report may evaluate:

- Continuity of therapeutic formulation.
- Use of previous disclosures.
- Review of agreed homework.
- Adaptation to client feedback.
- Consistency of ACT principles.
- Responsiveness across sessions.
- Continuity of the therapeutic relationship.
- Evidence of therapeutic flexibility.
- Changes in intervention strategy.
- Appropriate management of uncertainty.
- Limitations across the available sessions.

It must not infer long-term clinical effectiveness from three simulated sessions.

### 16.5 Response

HTTP status: `201 Created`

```json
{
  "data": {
    "evaluation_id": "uuid",
    "evaluation_scope": "longitudinal",
    "run_id": "uuid",
    "status": "completed",
    "evaluated_sessions": 3,
    "rubric_id": "ACT_LONGITUDINAL_RUBRIC_V0",
    "rubric_version": "0.2",
    "created_at": "2026-11-14T14:00:00Z"
  }
}
```

### 16.6 Duplicate Handling

A repeated request with the same run, completed session set, transcript manifest, and rubric version must return the existing canonical report.

The initial MVP does not support arbitrary re-evaluation revisions.

---

## 17. Retrieve Longitudinal Evaluations

### Endpoint

`GET /api/v1/simulation-runs/{run_id}/evaluations`

Purpose:

Retrieve evaluation reports associated with a simulation run.

The response must distinguish:

- Session-level evaluations.
- Longitudinal evaluations.

Each result should include:

- evaluation_id
- evaluation_scope
- session_id, when applicable
- run_id
- rubric_id
- rubric_version
- status
- created_at

---

## 18. Retrieve Evaluation Report

### Endpoint

`GET /api/v1/evaluations/{evaluation_id}`

Purpose:

Retrieve the complete authorized evaluation report.

Response fields:

- evaluation_id
- evaluation_scope
- run_id
- session_id, when applicable
- rubric_id
- rubric_version
- overall_summary
- competency_results
- strengths
- improvement_areas
- evidence_references
- missing_evidence
- alternative_responses
- safety_observations
- uncertainty_notes
- created_at

### 18.1 Evidence Requirements

Every evidence reference must identify:

- message_id
- message role
- evidence excerpt or span
- relevant competency

Evidence references must resolve to messages belonging to the evaluated session or to one of the sessions included in the longitudinal report.

The report must not contain invented transcript evidence.

### 18.2 Evaluation Limitations

The report is formative educational feedback.

It must not be described as:

- Validated therapist competence.
- Professional certification.
- A clinical diagnosis.
- Proof of successful psychotherapy.
- A validated measure of real-world treatment effectiveness.

---

# PART VI — INTERNAL SERVICE CONTRACTS

## 19. Orchestrator Interface

The Orchestrator manages the simulation lifecycle.

Responsibilities:

- Create simulation runs.
- Initialize sequential sessions.
- Coordinate therapist interactions.
- Coordinate Patient Context construction.
- Invoke Patient Agent.
- Coordinate output validation.
- Trigger deterministic event processing.
- Coordinate state validation.
- Complete sessions.
- Trigger evaluation generation.
- Coordinate memory persistence.

The Orchestrator must not directly invent psychological state changes.

Suggested internal operations:

- `create_run(...)`
- `create_next_session(...)`
- `process_interaction(...)`
- `complete_session(...)`
- `evaluate_session(...)`
- `evaluate_run(...)`

These are internal methods, not public HTTP routes.

---

## 20. Patient Context Service Interface

Method:

`build_patient_context(run_id, session_id)`

Responsibilities:

1. Retrieve the correct case version.
2. Retrieve restricted patient information.
3. Retrieve relevant case facts.
4. Retrieve disclosure statuses.
5. Retrieve current clinical state.
6. Retrieve relevant longitudinal memory.
7. Retrieve recent transcript messages.
8. Apply the disclosure policy.
9. Construct a validated PatientContext.
10. Exclude unrelated or unauthorized information.

This service is the authorized access path to `case_vault.db`.

It must return a typed object rather than an unrestricted database connection.

---

## 21. Patient Agent Interface

Method:

`generate_response(patient_context, therapist_message)`

Input:

- Validated PatientContext.
- Latest TherapistMessage.

Output:

- PatientResponse.
- Optional candidate interaction annotations.
- Model execution metadata.

Restrictions:

- No direct state modification.
- No direct database access.
- No arbitrary tool execution.
- No unrestricted filesystem access.
- No disclosure of hidden prompts.
- No automatic confirmation of case fact disclosure.

---

## 22. Event Processing Service Interface

Method:

`process_interaction(transcript_segment, application_events)`

Responsibilities:

- Record application-generated operational events.
- Collect optional behavioral event proposals.
- Validate message references.
- Preserve uncertainty.
- Prevent duplicate events.
- Submit eligible evidence to the State Engine.

The initial MVP prioritizes deterministic application events.

Model-assisted behavioral event extraction is optional and deferred.

The Event Processing Service is not an independently deployed service or mandatory third LLM Agent.

---

## 23. Clinical State Engine Interface

Method:

`validate_transition(current_state, proposal, evidence)`

Input:

- Current state snapshot.
- Candidate transition.
- Validated evidence.
- Versioned transition rules.

Output:

- Accepted transition.
- Rejected transition.
- Requires-review decision.
- New snapshot when applicable.

The State Engine is the only component authorized to modify canonical clinical state.

All accepted changes must be transactional and auditable.

---

## 24. Memory Service Interface

Initial methods:

- `retrieve_memory(run_id, session_id)`
- `create_memory_candidates(transcript, accepted_events)`
- `validate_memory_updates(candidates)`
- `persist_memory_updates(accepted_items)`

The Memory Service must:

- Preserve source message references.
- Distinguish disclosed facts from hypotheses.
- Maintain historical versions.
- Avoid fabricating events.
- Select only relevant information for PatientContext.

Memory processing is an internal backend responsibility in the initial MVP.

---

## 25. Evaluation Service Interface

Methods:

- `evaluate_session(session_id, rubric_version_id)`
- `evaluate_run(run_id, rubric_version_id)`

Responsibilities:

- Validate evaluation eligibility.
- Construct the appropriate EvaluationInput.
- Enforce the Evaluator Agent's information boundary.
- Invoke Evaluator Agent.
- Validate competency identifiers.
- Validate ratings.
- Validate transcript evidence.
- Persist completed reports.
- Record execution metadata.
- Handle evaluation failures.

The same Evaluator Agent may process both evaluation scopes through separate validated input schemas.

---

## 26. Evaluator Agent Interface

Method:

`evaluate(evaluation_input)`

Input:

- Session-level EvaluationInput or longitudinal EvaluationInput.
- Explicit rubric version.
- Finalized transcript data.
- Authorized therapist-visible context.

Output:

- EvaluationReport.

The Evaluator Agent must not have access to restricted database connections, unrestricted repositories, or hidden Patient Agent context.

---

# PART VII — ACCESS CONTROL AND SECURITY

## 27. External API Access Boundaries

The Therapist Interface may access:

- Approved case introductions.
- Simulation metadata.
- Session metadata.
- Therapist-visible conversation messages.
- Completed evaluation reports.

It must not access:

- Restricted clinical formulation.
- Hidden case facts.
- Internal disclosure policies.
- Private clinical state values.
- Unvalidated candidate events.
- Patient Agent prompts.
- Internal model reasoning.
- Internal memory records.

Access restrictions must be enforced by backend authorization and response serialization.

### 27.1 Local Single-User Configuration

The initial deployment is local single-user.

Requirements:

- Bind the API to `127.0.0.1` by default.
- Do not expose restricted databases through static file serving.
- Do not send hidden case information to external services.
- Do not include secrets in agent prompts.
- Validate all incoming requests.

Localhost binding must not be described as complete security against unauthorized processes on the same computer.

---

## 28. Prompt Injection and Untrusted Inputs

Therapist messages and transcript content must be treated as untrusted data.

Agents must not obey conversational instructions that attempt to:

- Reveal hidden prompts.
- Reveal restricted case information.
- Modify evaluation rubrics.
- Bypass access boundaries.
- Execute operating-system commands.
- Modify canonical state.
- Access database contents.

Prompt wording must be supported by application-level restrictions.

The backend must validate both agent inputs and outputs.

---

# PART VIII — ERROR HANDLING

## 29. Standard Error Codes

Initial API error codes:

| Error Code | Meaning |
|---|---|
| VALIDATION_ERROR | Invalid request data |
| RESOURCE_NOT_FOUND | Requested resource does not exist |
| CASE_NOT_AVAILABLE | Case is unavailable |
| INVALID_CASE_VERSION | Case version is invalid |
| SESSION_NOT_ACTIVE | Session does not accept messages |
| SESSION_ORDER_INVALID | Previous session is incomplete |
| RUN_NOT_COMPLETE | Run is not eligible for longitudinal evaluation |
| DUPLICATE_REQUEST | Duplicate operation detected |
| IDEMPOTENCY_CONFLICT | Same key used with a different payload |
| REQUEST_IN_PROGRESS | Original request is still being processed |
| MODEL_EXECUTION_FAILED | Local model execution failed |
| COMPONENT_UNAVAILABLE | Required component is unavailable |
| EVALUATION_NOT_ALLOWED | Evaluation preconditions are not satisfied |
| ACCESS_DENIED | Operation is not authorized |
| OUTPUT_VALIDATION_FAILED | Model output failed validation |
| STATE_VALIDATION_FAILED | State transition failed validation |
| INTERNAL_ERROR | Unexpected internal error |

### 29.1 HTTP Status Mapping

| HTTP Status | Typical Use |
|---|---|
| 200 | Successful retrieval or replay of completed operation |
| 201 | New resource or operation successfully created |
| 202 | Operation remains in progress |
| 400 | Invalid request |
| 403 | Access denied |
| 404 | Resource not found |
| 409 | State conflict or idempotency conflict |
| 422 | Schema validation failure |
| 500 | Unexpected internal error |
| 503 | Required component unavailable |

HTTP status codes must remain consistent across endpoint implementations.

### 29.2 Error Information

Errors must not expose:

- Hidden case context.
- Internal prompts.
- Full model input.
- Database connection strings.
- Stack traces.
- Application secrets.

---

## 30. Concurrency and Recovery

The initial MVP allows only one active message-generation operation per session.

The backend must prevent:

- Duplicate message sequence numbers.
- Duplicate patient responses.
- Concurrent conflicting state updates.
- Simultaneous completion and message generation.
- Duplicate disclosure confirmation.
- Duplicate evaluation creation.

### 30.1 Recovery Requirements

After an interrupted operation:

1. Retrieve the original request record.
2. Check whether the therapist message exists.
3. Check whether a patient response was persisted.
4. Determine whether generation is still active.
5. Determine whether a controlled retry is permitted.
6. Reuse the original idempotency identity.
7. Preserve audit history.

The system must never assume that a timeout proves that model generation did not happen.

---

# PART IX — API TESTING

## 31. Required API Tests

The initial test suite must verify:

1. Case listing excludes restricted fields.
2. Case retrieval returns only authorized information.
3. Simulation run creation works.
4. Case version references remain consistent.
5. Sessions are created in sequential order.
6. A later session cannot start before its predecessor completes.
7. Session numbering remains sequential for any number of sessions.
8. Therapist messages are stored correctly.
9. Duplicate interaction requests do not create duplicate persisted messages.
10. Reusing an idempotency key with a different payload is rejected.
11. Failed patient generation does not invalidate the therapist message.
12. Interaction status can be retrieved.
13. Completed sessions reject new therapist messages.
14. Completed sessions can be evaluated.
15. Longitudinal evaluation only uses completed, finalized transcripts in its selected scope.
16. Longitudinal evaluation supports variable session counts and uses every transcript version in scope.
17. Evaluator input excludes restricted case information.
18. Evaluation evidence references valid messages.
19. Invalid rating values are rejected.
20. Invalid evidence references are rejected.
23. Standard error responses are preserved.
24. Database and application failures do not create partially accepted state transitions.

### 31.1 Security Tests

Specific tests must verify:

- No hidden case information in frontend responses.
- No PatientContext in evaluator input.
- No arbitrary agent tool access.
- No unauthorized state modification.
- No secret exposure through logs.
- No public access to database files.

---

## 32. API Documentation

FastAPI generates development API documentation automatically.

Initial development endpoints:

- `/docs`
- `/redoc`
- `/openapi.json`

These endpoints must be reviewed before any later production deployment.

The OpenAPI specification must reflect the actual implemented Pydantic schemas and endpoint behavior.

Documentation must not claim functionality that has not been implemented.

---

## 33. Initial MVP Endpoint Summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend health |
| GET | `/api/v1/cases` | List available cases |
| GET | `/api/v1/cases/{case_id}` | Retrieve authorized case profile |
| POST | `/api/v1/simulation-runs` | Create simulation run |
| GET | `/api/v1/simulation-runs/{run_id}` | Retrieve run |
| GET | `/api/v1/simulation-runs` | List persisted simulation runs |
| POST | `/api/v1/simulation-runs/{run_id}/start` | Start run |
| POST | `/api/v1/simulation-runs/{run_id}/interrupt` | Interrupt active run |
| POST | `/api/v1/simulation-runs/{run_id}/resume` | Resume interrupted run |
| POST | `/api/v1/simulation-runs/{run_id}/complete` | Complete eligible run |
| GET | `/api/v1/simulation-runs/{run_id}/sessions` | List sessions |
| POST | `/api/v1/simulation-runs/{run_id}/sessions` | Create next sequential session |
| GET | `/api/v1/sessions/{session_id}` | Retrieve session |
| GET | `/api/v1/sessions/{session_id}/messages` | Retrieve therapist-visible transcript |
| POST | `/api/v1/sessions/{session_id}/messages` | Submit therapist message |
| GET | `/api/v1/interaction-requests/{request_id}` | Retrieve interaction operation status |
| POST | `/api/v1/sessions/{session_id}/complete` | Complete session |
| POST | `/api/v1/sessions/{session_id}/evaluations` | Generate session-level evaluation |
| GET | `/api/v1/sessions/{session_id}/evaluations` | List session evaluations |
| POST | `/api/v1/simulation-runs/{run_id}/evaluations` | Generate longitudinal evaluation |
| GET | `/api/v1/simulation-runs/{run_id}/evaluations` | List run evaluations |
| GET | `/api/v1/evaluations/{evaluation_id}` | Retrieve evaluation report |
| GET | `/api/v1/simulation-runs/{run_id}/memories` | List Run memory and evidence |
| POST | `/api/v1/simulation-runs/{run_id}/memories/candidates` | Create evidence-validated review candidate |
| POST | `/api/v1/simulation-runs/{run_id}/memories/{memory_id}/review` | Accept or reject a memory candidate |

Disclosure management, hidden patient state, direct access to internal clinical state, and restricted case access remain outside the public Therapist Interface API. The explicit run and session lifecycle operations documented here are the supported public state-transition controls.

---

## 34. Initial Implementation Scope

The first API implementation must support:

- Versioned REST API.
- Case listing.
- Authorized case metadata retrieval.
- Simulation run creation.
- Simulation run listing and workspace recovery.
- Explicit run lifecycle controls (start, interrupt, resume, complete).
- Sequential sessions with no universal fixed count.
- Session retrieval.
- Message submission.
- Patient Agent response delivery.
- Idempotent message submission.
- Interaction recovery status.
- Session completion.
- Session-level evaluation.
- Longitudinal evaluation.
- Evaluation report retrieval.
- Standard error handling.
- Restricted information isolation.
- Automated API tests.

Advanced streaming, multi-user authentication, external model APIs, and distributed services are outside the initial MVP scope.

---

## 35. Open Implementation Questions

The following issues remain for the implementation phase:

- Should model generation timeout values differ by agent?
- How should interrupted model generation be recovered?
- How should model-specific output parsing be normalized?
- How should the application handle simultaneous evaluation requests?
- How should transcript content hashes be generated?
- Which endpoints require stronger authentication before multi-user deployment?
- Should event processing run immediately after each interaction or at session completion?
- How should memory update failures be retried?
- How should the OpenAPI contract be compared with implementation changes?

These decisions must be resolved through implementation and testing.

---

---

# PART X — LONGITUDINAL MEMORY API

## 36. List Run Memory

`GET /api/v1/simulation-runs/{run_id}/memories`

The optional `status` filter accepts `active`, `superseded`, `requires_review`, or `rejected`. Each result includes its information class, scope, version and supersession link, plus cited message identifiers and validated excerpts when available.

Only active memory is eligible for PatientContext retrieval. Rejected, superseded, and review-pending items remain available for authorized audit and learning workflows.

## 37. Create Memory Candidate

`POST /api/v1/simulation-runs/{run_id}/memories/candidates`

The request identifies the source session, a completed interaction request, a backend-scoped proposal index, memory scope, a structured proposal and exact quoted message evidence. The backend verifies Run ownership, chronology, patient-authored evidence for client-fact classes, and exact excerpt offsets. The proposal's identifier is not used as a database identity.

Candidates are always stored as `requires_review`, regardless of the proposal's suggested status. Candidate creation is idempotent for a completed interaction request and proposal index; a changed payload at that identity returns a conflict.

## 38. Review Memory Candidate

`POST /api/v1/simulation-runs/{run_id}/memories/{memory_id}/review`

The request contains `decision` (`accepted` or `rejected`) and a non-empty rationale. The client cannot supply a reviewer identity. In the unauthenticated, single-user API, the backend records the explicit sentinel `unverified_local_caller`; it does not claim that a person was authenticated. The decision and rationale are persisted as an immutable review record. Acceptance makes the candidate active; rejection makes it inactive and terminal. Accepting a revision atomically supersedes its active predecessor. Conflicting review decisions return `409 Conflict`.

Authenticated multi-user review requires an authenticated identity dependency before replacing this sentinel with a person-specific identifier.

## 39. Get Memory Extraction Status

`GET /api/v1/simulation-runs/{run_id}/memories/processing/{interaction_request_id}`

Returns the sanitized status, attempt count, candidate count, and last error code for the Run-owned extraction job. The request creates one pending job atomically with a successfully completed interaction. A local worker processes only the current therapist/patient exchange, outside the interaction transaction. Generated proposals are schema-validated and transcript-evidence-checked, stored as `requires_review`, and never activated automatically. If the local model is not configured, pending work remains durable and visible through this endpoint.

Retries use leases and exponential backoff, with a five-attempt limit. Validated proposal output is saved before candidate persistence so a worker crash can replay the same proposals idempotently. Terminal failures expose a sanitized error code; model output and transcript text are not returned by this status endpoint.

**End of Document**
