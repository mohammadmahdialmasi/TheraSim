# TheraSim — API Contracts

**Document Version:** 0.1
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the API contracts for communication between the TheraSim frontend, backend services, and internal simulation components.

The purpose is to establish:

- Consistent communication between system components.
- Explicit request and response structures.
- Predictable session lifecycle management.
- Controlled access to simulation data.
- Protection against unauthorized disclosure of restricted case information.
- Traceable API operations.
- Consistent error handling.
- Compatibility between frontend and backend versions.

The initial API will be implemented using FastAPI.

The API contracts are logical specifications. Exact Pydantic models and executable route definitions will be developed during implementation.

---

## 2. API Architecture

TheraSim uses a backend-mediated architecture.

The frontend communicates with the backend API. The backend coordinates internal components through explicit service interfaces.

### 2.1 Communication Flow

1. The Therapist Interface submits a request to the API.
2. The API validates the request.
3. The Orchestrator processes the operation.
4. The required internal component is invoked.
5. The result is validated.
6. Authorized data is persisted.
7. The API returns a structured response.

The frontend must not communicate directly with:

- Ollama.
- Patient Agent internals.
- Evaluator Agent internals.
- SQLite databases.
- Restricted case storage.
- Clinical State Engine internals.

All communication must pass through authorized backend interfaces.

### 2.2 API Categories

The architecture defines two categories:

**A. External API**

Endpoints used by the Therapist Interface.

**B. Internal Service Contracts**

Interfaces used between the Orchestrator, Patient Agent, Evaluator Agent, State Engine, Memory Service, and repository layer.

Internal service contracts do not automatically need to be exposed as HTTP endpoints.

---

## 3. API Conventions

### 3.1 Base URL

Initial local development:

`http://127.0.0.1:8000`

### 3.2 API Versioning

All application endpoints must use versioned paths.

Initial API prefix:

`/api/v1`

Example:

`/api/v1/sessions`

Breaking changes must be introduced through a new API version or an explicitly managed compatibility migration.

### 3.3 HTTP Methods

| Method | Purpose |
|---|---|
| GET | Retrieve resources |
| POST | Create resources or execute operations |
| PATCH | Modify permitted resource attributes |
| DELETE | Delete resources when explicitly authorized |

The initial MVP should favor POST and GET for the main simulation workflow. Historical records must not be silently overwritten or deleted.

### 3.4 Content Type

JSON is the standard request and response format.

Default content type:

`application/json`

### 3.5 Identifiers

Resource identifiers use UUID strings.

### 3.6 Timestamps

All timestamps use UTC and ISO 8601 representation with timezone information.

Example:

`2026-11-14T12:30:00Z`

### 3.7 Pagination

Collection endpoints should support pagination when needed.

Initial parameters:

- limit
- offset

The API must enforce a maximum page size.

---

## 4. Standard Response Structure

Successful responses must use consistent structures.

### 4.1 Single Resource Response

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

All API errors must use a consistent structure.

Example:

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

The `code` field must be stable and suitable for frontend error handling.

The `message` field must be understandable to the user or developer, depending on the error context.

Internal stack traces, restricted case information, hidden prompts, and sensitive model context must never appear in external error responses.

---

## 5. External API — Case Management

### 5.1 List Available Cases

**Endpoint:**

`GET /api/v1/cases`

Purpose:

Retrieve cases available for simulation.

Query parameters:

- limit
- offset
- modality
- language

Response fields:

- case_id
- case_code
- display_name
- modality
- available_languages
- available_case_versions
- status

The endpoint must return only cases approved for simulation.

Restricted case formulations and undisclosed personal history must not be included.

### 5.2 Retrieve Case Information

**Endpoint:**

`GET /api/v1/cases/{case_id}`

Purpose:

Retrieve authorized case metadata.

The response may contain a therapist-facing case introduction if that introduction is explicitly designated for disclosure.

It must not include:

- Hidden clinical formulation.
- Undisclosed personal history.
- Internal Patient Agent instructions.
- Restricted simulation context.
- Future planned responses.

---

## 6. External API — Simulation Runs

### 6.1 Create Simulation Run

**Endpoint:**

`POST /api/v1/simulation-runs`

Purpose:

Create a longitudinal simulation run for a selected synthetic case.

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

The case version may be selected automatically by the backend when omitted.

The backend must validate case availability and modality compatibility.

Response:

```json
{
  "data": {
    "run_id": "uuid",
    "case_id": "uuid",
    "case_version_id": "uuid",
    "status": "initialized",
    "created_at": "2026-11-14T12:30:00Z"
  }
}
```

### 6.2 Retrieve Simulation Run

**Endpoint:**

`GET /api/v1/simulation-runs/{run_id}`

Purpose:

Retrieve authorized simulation metadata.

The response may include:

- run_id
- case_id
- status
- modality
- language
- created_at
- started_at
- completed_at
- session_count

It must not expose restricted clinical state or hidden case information.

### 6.3 List Simulation Sessions

**Endpoint:**

`GET /api/v1/simulation-runs/{run_id}/sessions`

Purpose:

Retrieve the sessions associated with a simulation run.

Response fields:

- session_id
- session_number
- status
- started_at
- ended_at

The endpoint must preserve chronological ordering.

---

## 7. External API — Session Management

### 7.1 Create Session

**Endpoint:**

`POST /api/v1/simulation-runs/{run_id}/sessions`

Purpose:

Create a new session within an existing simulation run.

Request:

```json
{
  "session_number": 1
}
```

The backend must verify:

- The simulation run exists.
- The run is not completed or failed.
- The requested session number is permitted.
- The previous session has reached an allowed terminal state.
- The appropriate case version and longitudinal memory are available.

Response:

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

Initial Patient Agent context must be prepared through the authorized Patient Context component.

### 7.2 Retrieve Session

**Endpoint:**

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

The response must not contain hidden agent context or internal state variables.

### 7.3 Retrieve Session Messages

**Endpoint:**

`GET /api/v1/sessions/{session_id}/messages`

Purpose:

Retrieve the authorized therapist-visible conversation.

Query parameters:

- limit
- offset

Response:

```json
{
  "data": [
    {
      "message_id": "uuid",
      "sequence_number": 1,
      "role": "therapist",
      "content": "Can you tell me more about that experience?",
      "created_at": "2026-11-14T12:31:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 1
  }
}
```

Only messages authorized for therapist visibility may be returned.

---

## 8. External API — Therapist Interaction

### 8.1 Submit Therapist Message

**Endpoint:**

`POST /api/v1/sessions/{session_id}/messages`

Purpose:

Submit a therapist message and obtain a Patient Agent response.

Request:

```json
{
  "content": "Can you describe what happened during that meeting?"
}
```

Required fields:

- content

Optional request header:

`Idempotency-Key: unique-operation-key`

### Processing Sequence

1. Validate the session.
2. Verify that the session is active.
3. Validate message length and content format.
4. Check the idempotency key.
5. Persist the therapist message.
6. Prepare authorized Patient Agent context.
7. Generate the patient response.
8. Validate the PatientResponse structure.
9. Persist the patient response.
10. Trigger the authorized event-processing workflow.
11. Return the interaction result.

### Response

```json
{
  "data": {
    "therapist_message": {
      "message_id": "uuid",
      "role": "therapist",
      "content": "Can you describe what happened during that meeting?"
    },
    "patient_response": {
      "message_id": "uuid",
      "role": "patient",
      "content": "I remember feeling embarrassed when my colleague interrupted me."
    },
    "session_status": "active"
  }
}
```

### Failure Handling

If model generation fails after the therapist message has been persisted:

- The therapist message must remain stored.
- The failed generation must be recorded.
- The session must not be marked completed.
- The API must return a structured error.
- A retry must not duplicate the therapist message when the same idempotency key is used.

The backend must distinguish between a failed model operation and a successfully completed interaction.

The initial MVP may use synchronous message submission. If generation latency makes synchronous requests unreliable, a background job and polling mechanism may be introduced in a later API version.

---

## 9. External API — Session Completion

### 9.1 Complete Session

**Endpoint:**

`POST /api/v1/sessions/{session_id}/complete`

Purpose:

Terminate the current simulation session.

Request:

```json
{
  "completion_reason": "normal"
}
```

Possible completion reasons:

- normal
- trainee_ended
- system_interrupted

The backend must:

1. Verify that the session is active.
2. Persist all completed interaction records.
3. Finalize the transcript version.
4. Record the completion timestamp.
5. Update the session status.
6. Create an audit event.

Response:

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

Session completion and evaluation generation must be separate operations.

An evaluation failure must not invalidate an already completed session.

---

## 10. External API — Evaluation

### 10.1 Generate Evaluation

**Endpoint:**

`POST /api/v1/sessions/{session_id}/evaluations`

Purpose:

Generate an evaluation report for a completed simulation session.

Request:

```json
{
  "rubric_id": "ACT_RUBRIC_V0",
  "rubric_version": "0.1"
}
```

The backend must verify:

- The session is completed.
- A compatible rubric exists.
- The transcript is finalized.
- An evaluation has not already been created for the same operation unless a new evaluation is explicitly requested.

The Evaluator Agent receives only:

- Authorized session transcript.
- Applicable evaluation rubric.
- Therapist-visible context.
- Explicit evaluation instructions.

It must never receive restricted case formulation or hidden Patient Agent instructions.

Response:

```json
{
  "data": {
    "evaluation_id": "uuid",
    "session_id": "uuid",
    "status": "completed",
    "rubric_id": "ACT_RUBRIC_V0",
    "rubric_version": "0.1",
    "created_at": "2026-11-14T13:05:00Z"
  }
}
```

The initial MVP may generate the evaluation synchronously. Long-running evaluation operations may later use an asynchronous job pattern.

### 10.2 Retrieve Evaluation Report

**Endpoint:**

`GET /api/v1/evaluations/{evaluation_id}`

Purpose:

Retrieve an authorized evaluation report.

The report may contain:

- evaluation_id
- session_id
- overall_summary
- competency_results
- strengths
- improvement_areas
- evidence_references
- missing_evidence
- safety_observations
- uncertainty_notes
- created_at

The API must preserve evidence references to transcript messages.

The report must not claim validated therapist competence or provide clinical certification.

### 10.3 List Session Evaluations

**Endpoint:**

`GET /api/v1/sessions/{session_id}/evaluations`

Purpose:

Retrieve evaluations associated with a session.

Multiple evaluations may exist when different rubric versions or explicitly requested re-evaluations are used.

---

## 11. Internal Service Contracts

Internal service contracts define how the Orchestrator coordinates the system.

They do not imply that every internal operation requires an independently accessible HTTP endpoint.

### 11.1 Orchestrator Interface

Responsibilities:

- Create simulation runs.
- Initialize sessions.
- Process therapist messages.
- Coordinate Patient Agent execution.
- Trigger event extraction.
- Invoke State Engine validation.
- Complete sessions.
- Trigger evaluation.
- Coordinate persistence.

The Orchestrator must not independently invent clinical state changes.

### 11.2 Patient Agent Interface

**Method:**

`generate_response(context, therapist_message)`

Input:

- authorized case context
- current simulation state
- relevant longitudinal memory
- current session context
- latest therapist message

Output:

- PatientResponse
- permitted structured annotations
- generation metadata

Restrictions:

- Must not return hidden prompts as conversation content.
- Must not invent established personal history outside the case definition.
- Must preserve continuity across sessions.
- Must distinguish explicit disclosures from internal simulation assumptions.

### 11.3 Patient Context Interface

**Method:**

`build_patient_context(case_version_id, run_id, session_id)`

Purpose:

Build the minimum authorized context required by the Patient Agent.

Responsibilities:

- Retrieve relevant case information.
- Include the current state.
- Retrieve relevant longitudinal memory.
- Apply disclosure constraints.
- Exclude information not required for the current interaction.

This interface is the authorized access path to the restricted case database.

It must not provide unrestricted database access to the Patient Agent.

### 11.4 Event Extraction Interface

**Method:**

`extract_events(transcript_segment, context)`

Input:

- relevant transcript messages
- authorized event extraction instructions
- event schema version

Output:

- candidate events
- evidence references
- extraction metadata
- uncertainty notes

The extraction layer may use deterministic rules, language models, or both.

It must not directly modify the canonical clinical state.

### 11.5 Clinical State Engine Interface

**Method:**

`validate_transitions(current_state, candidate_transitions, evidence)`

Input:

- current structured state
- candidate transitions
- accepted event records
- relevant transcript evidence
- transition rule version

Output:

- accepted transitions
- rejected transitions
- transitions requiring review
- resulting state snapshot, when applicable

The Clinical State Engine must enforce deterministic validation rules.

### 11.6 Evaluator Agent Interface

**Method:**

`evaluate_session(evaluation_input)`

Input:

- authorized transcript
- versioned evaluation rubric
- therapist-visible session context
- evaluation instructions

Output:

- EvaluationReport
- competency results
- supporting evidence references
- uncertainty notes
- missing evidence

The evaluator must not have access to restricted case storage.

### 11.7 Memory Service Interface

**Methods:**

- `retrieve_memory(run_id, session_id)`
- `create_memory_candidates(transcript, events)`
- `validate_memory_updates(candidates)`
- `persist_memory_updates(accepted_items)`

Memory records must preserve their source and information classification.

A memory update must not silently convert a therapist hypothesis into a disclosed client fact.

---

## 12. Access Control

The API must enforce access boundaries at the backend.

### 12.1 External Access

The Therapist Interface may access:

- Approved case introductions.
- Simulation metadata.
- Session metadata.
- Therapist-visible transcript messages.
- Completed evaluation reports.

It must not access:

- Hidden case formulation.
- Restricted personal history.
- Patient Agent internal prompts.
- Internal clinical state variables.
- Candidate event annotations.
- Unvalidated state transitions.
- Restricted memory records.

### 12.2 Internal Access

| Component | Authorized Access |
|---|---|
| Orchestrator | Coordination and authorized service interfaces |
| Patient Context | Restricted case data through controlled access |
| Patient Agent | Minimum required patient context |
| Evaluator Agent | Transcript, rubric, authorized session context |
| State Engine | Structured state, candidate events, evidence |
| Memory Service | Authorized longitudinal memory operations |
| Repository Layer | Data access according to explicit repository boundaries |

Internal components must receive typed objects rather than unrestricted database access whenever possible.

### 12.3 Local-First Security

The initial application is designed for local single-user operation.

Initial security requirements:

- Bind the development server to localhost by default.
- Do not expose the API to the public network by default.
- Keep restricted database files outside frontend-accessible directories.
- Never embed database credentials or unrestricted internal configuration in frontend code.
- Validate every incoming request.
- Avoid logging hidden prompts or restricted case content.

Before multi-user or network access is introduced, authentication, authorization, encryption, and stronger process isolation must be designed and implemented.

Localhost binding alone must not be treated as complete protection against unauthorized access.

---

## 13. Idempotency and Concurrency

Operations that create messages, sessions, evaluations, or state transitions must handle duplicate requests safely.

### 13.1 Idempotency

The following operations should support idempotency keys:

- Therapist message submission.
- Session creation.
- Evaluation generation.
- Other operations that may create duplicate records during retries.

A repeated request with the same idempotency key and identical payload must not create duplicate resources.

Reusing the same key with a different payload must return a conflict error.

### 13.2 Concurrency

The initial MVP may limit each session to one active interaction request at a time.

The backend must prevent:

- Two simultaneous therapist messages from corrupting sequence ordering.
- Duplicate Patient Agent responses.
- Concurrent conflicting state transitions.
- Multiple session-completion operations from creating inconsistent records.

Operations requiring multiple database writes must use appropriate transactions.

---

## 14. Standard Error Codes

Initial API error codes:

| Error Code | Meaning |
|---|---|
| VALIDATION_ERROR | Invalid request data |
| RESOURCE_NOT_FOUND | Requested resource does not exist |
| CASE_NOT_AVAILABLE | Case is not available for simulation |
| SESSION_NOT_ACTIVE | Session does not accept new messages |
| RUN_ALREADY_COMPLETED | Simulation run is already completed |
| DUPLICATE_REQUEST | Duplicate operation detected |
| IDEMPOTENCY_CONFLICT | Same idempotency key used with different payload |
| MODEL_EXECUTION_FAILED | Language-model execution failed |
| COMPONENT_UNAVAILABLE | Required internal component is unavailable |
| EVALUATION_NOT_ALLOWED | Session is not eligible for evaluation |
| ACCESS_DENIED | Operation is not authorized |
| STATE_VALIDATION_FAILED | State transition failed validation |
| INTERNAL_ERROR | Unexpected internal error |

Suggested HTTP status mapping:

| HTTP Status | Typical Use |
|---|---|
| 200 | Successful retrieval or operation |
| 201 | Resource created |
| 202 | Operation accepted for asynchronous processing |
| 400 | Invalid request |
| 403 | Access denied |
| 404 | Resource not found |
| 409 | State conflict or duplicate operation |
| 422 | Request validation failure |
| 500 | Unexpected server error |
| 503 | Required component unavailable |

The external error response must not reveal whether restricted case information exists unless that information is already authorized for the requester.

---

## 15. API Documentation and Testing

FastAPI should expose generated OpenAPI documentation during development.

Initial documentation endpoints:

- `/docs`
- `/redoc`
- `/openapi.json`

These endpoints should be disabled or restricted appropriately in any later production deployment.

### Required API Tests

The initial test suite must verify:

1. Case listing does not expose restricted fields.
2. Simulation run creation works with valid input.
3. Sessions are created in the correct order.
4. Therapist messages are stored correctly.
5. Patient Agent failures do not corrupt stored messages.
6. Duplicate message requests do not create duplicate interactions.
7. Inactive sessions reject new messages.
8. Completed sessions reject further therapist messages.
9. Evaluation cannot run on an incomplete session.
10. Evaluator inputs exclude hidden case information.
11. Evaluation evidence references valid transcript messages.
12. Unauthorized requests are rejected.
13. State transitions do not bypass validation.
14. API errors use the standard response structure.

---

## 16. Initial MVP Endpoint Summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/v1/cases` | List available cases |
| GET | `/api/v1/cases/{case_id}` | Retrieve authorized case metadata |
| POST | `/api/v1/simulation-runs` | Create simulation run |
| GET | `/api/v1/simulation-runs/{run_id}` | Retrieve simulation run |
| GET | `/api/v1/simulation-runs/{run_id}/sessions` | List sessions |
| POST | `/api/v1/simulation-runs/{run_id}/sessions` | Create session |
| GET | `/api/v1/sessions/{session_id}` | Retrieve session |
| GET | `/api/v1/sessions/{session_id}/messages` | Retrieve transcript messages |
| POST | `/api/v1/sessions/{session_id}/messages` | Submit therapist message |
| POST | `/api/v1/sessions/{session_id}/complete` | Complete session |
| POST | `/api/v1/sessions/{session_id}/evaluations` | Generate evaluation |
| GET | `/api/v1/sessions/{session_id}/evaluations` | List session evaluations |
| GET | `/api/v1/evaluations/{evaluation_id}` | Retrieve evaluation report |

The `/health` endpoint may return basic service status only. It must not expose database contents, model configuration secrets, or restricted case information.

State transition, hidden memory, and restricted case-management endpoints are intentionally excluded from the therapist-facing API in the initial MVP.

---

## 17. Open Design Questions

The following decisions remain to be finalized:

- Should interaction generation use synchronous responses or asynchronous jobs?
- Should server-sent events be introduced for streamed patient responses?
- How should model generation timeouts be handled?
- How should interrupted message operations be recovered?
- Should session access use additional authorization tokens in local single-user mode?
- Which internal services should remain in-process?
- When should internal service boundaries become separate processes?
- How should API compatibility be tested across frontend and backend versions?
- How should evaluation retries preserve reproducibility?
- How should API request and response schemas be versioned?

These questions must be addressed before implementation.

---

## 18. Initial Implementation Scope

The first API implementation will include:

- Versioned REST API.
- Case listing and authorized metadata retrieval.
- Simulation run creation.
- Session creation and retrieval.
- Therapist message submission.
- Patient Agent response delivery.
- Session completion.
- Evaluation generation and retrieval.
- Standard error handling.
- Idempotency for message submission.
- Strict access boundaries for restricted case information.
- Automated API tests.

Advanced streaming, multi-user authentication, distributed services, and external API providers are outside the initial MVP scope.

---

**End of Document**