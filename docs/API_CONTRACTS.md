# TheraSim — API Contracts

**Document Version:** 0.2
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14
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
  "language": "fa"
}
```

Required fields:

- case_id
- modality
- language

The case_version_id may be omitted when the backend can identify the approved active version.

The backend must verify:

- Case existence.
- Case availability.
- Case version compatibility.
- Supported therapeutic modality.
- Supported language.

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
- started_at
- completed_at
- created_at

Restricted patient state and hidden case information must not be exposed.

### 7.3 List Simulation Sessions

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
- Fewer than three sessions have been created.
- Previous sessions have reached an allowed completed state.
- The requested case version remains available.
- Required longitudinal context can be constructed.

Session numbering must be assigned by the backend:

1. Session 1
2. Session 2
3. Session 3

The MVP does not support arbitrary session insertion or session-number modification.

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

A request to create more than three sessions must be rejected.

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
13. Record deterministic application events.
14. Complete the InteractionRequest.
15. Return the interaction result.

Candidate behavioral event extraction is a separate internal process.

Failure of optional event extraction must not invalidate a successfully completed therapist-patient interaction.

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

Generate a final evaluation of the therapist's work across all three connected simulation sessions.

This is a required capability of the initial MVP.

### 16.1 Request

```json
{
  "rubric_id": "ACT_LONGITUDINAL_RUBRIC_V0",
  "rubric_version": "0.1"
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
3. Exactly three sessions have been completed.
4. All three transcripts are finalized.
5. Session ordering is valid.
6. No required transcript is missing.
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
- all three finalized session transcripts
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
    "rubric_version": "0.1",
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
| SESSION_LIMIT_REACHED | Three-session limit reached |
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
6. Session 2 cannot start before Session 1 completes.
7. Session 3 cannot start before Session 2 completes.
8. A fourth session cannot be created.
9. Therapist messages are stored correctly.
10. Duplicate interaction requests do not create duplicate persisted messages.
11. Reusing an idempotency key with a different payload is rejected.
12. Failed patient generation does not invalidate the therapist message.
13. Interaction status can be retrieved.
14. Completed sessions reject new therapist messages.
15. Completed sessions can be evaluated.
16. Longitudinal evaluation requires all three completed sessions.
17. Longitudinal evaluation uses all three transcript versions.
18. Evaluator input excludes restricted case information.
19. Evaluation evidence references valid messages.
20. Invalid rating values are rejected.
21. Invalid evidence references are rejected.
22. Unauthorized API requests are rejected.
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

Disclosure management, hidden memory, state transitions, and restricted case access are intentionally excluded from the public Therapist Interface API.

---

## 34. Initial Implementation Scope

The first API implementation must support:

- Versioned REST API.
- Case listing.
- Authorized case metadata retrieval.
- Simulation run creation.
- Three sequential sessions.
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

**End of Document**