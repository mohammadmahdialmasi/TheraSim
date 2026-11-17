# TheraSim — Database Schema

**Document Version:** 0.2
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14
**Architecture Reference:** MVP_DECISIONS.md
**Data Contract Reference:** DATA_CONTRACTS.md

---

## 1. Purpose

This document defines the logical database schema for the initial TheraSim MVP.

The database architecture must support:

- Synthetic case management.
- Versioned case definitions.
- Restricted case information isolation.
- Three sequential simulation sessions.
- Therapist and patient messages.
- Idempotent interaction requests.
- Disclosure tracking.
- Structured interaction events.
- Clinical state snapshots and transitions.
- Longitudinal memory.
- Session-level evaluations.
- Run-level longitudinal evaluations.
- Model and prompt execution metadata.
- Audit records.

The MVP uses two SQLite database files:

1. `therasim.db`
2. `case_vault.db`

This document defines the logical schema. Executable SQL migrations and repository implementations will be developed separately.

`MVP_DECISIONS.md` takes precedence over conflicting provisional database designs.

---

## 2. Database Architecture

### 2.1 Operational Database

**File:** `therasim.db`

Stores:

- Cases and case versions.
- Public case profiles.
- Simulation runs.
- Sessions.
- Messages.
- Interaction requests.
- Disclosure statuses and history.
- Events and evidence references.
- State snapshots.
- State transitions.
- Longitudinal memory.
- Rubric versions.
- Evaluation reports.
- Model execution metadata.
- Audit events.

### 2.2 Restricted Case Database

**File:** `case_vault.db`

Stores:

- Restricted case formulations.
- Undisclosed personal history.
- Individual case facts.
- Case hypotheses.
- Disclosure policies.
- Hidden simulation instructions.
- Restricted safety baseline information.

The Patient Context Service is the authorized access path to this database.

### 2.3 Cross-Database Relationships

SQLite foreign keys cannot enforce relationships between separate database files in the same way as tables within one database.

Therefore:

- Foreign keys within each database must be enforced by SQLite.
- Cross-database identifiers must be validated by application services.
- Each restricted record must reference an existing case version in the operational database.
- The Evaluator Agent must never receive a connection to the restricted database.

Separate database files provide logical separation, not complete security against a process or local user with unrestricted filesystem access.

---

## 3. Database Conventions

### 3.1 Identifier Format

Primary keys use UUID strings unless an explicitly defined case fact identifier is required.

Examples:

- case_id
- case_version_id
- run_id
- session_id
- message_id
- request_id
- event_id
- snapshot_id
- transition_id
- memory_id
- evaluation_id
- model_run_id

Case fact identifiers use stable strings such as:

- AVA-FACT-001
- AVA-FACT-002

### 3.2 Timestamp Format

All timestamps must:

- Use UTC.
- Follow ISO 8601.
- Include timezone information.
- Remain consistent across the application.

### 3.3 Structured Data

Structured fields may be stored as JSON-serialized TEXT.

Examples:

- generation_parameters
- profile_metadata
- event_payload
- variable_values
- evaluation_metadata
- restricted case formulation

All JSON values must be validated against their corresponding application schemas before persistence.

### 3.4 SQLite Requirements

The application must:

- Enable foreign key enforcement on every connection.
- Use parameterized SQL statements.
- Use transactions for related operations.
- Use explicit CHECK constraints.
- Use unique constraints where required.
- Validate data before writing.
- Preserve historical records.
- Handle database failures explicitly.

Required connection setting:

`PRAGMA foreign_keys = ON;`

---

# PART I — OPERATIONAL DATABASE

## 4. Case Management Tables

### 4.1 cases

Stores general metadata for synthetic cases.

| Field | Type | Constraints |
|---|---|---|
| case_id | TEXT | Primary Key |
| case_code | TEXT | Unique, Not Null |
| display_name | TEXT | Not Null |
| status | TEXT | Not Null |
| created_at | TEXT | Not Null |
| updated_at | TEXT | Not Null |

Possible statuses:

- draft
- active
- archived

Restricted formulation and undisclosed personal history must not be stored in this table.

### 4.2 case_versions

Stores versioned definitions of synthetic cases.

| Field | Type | Constraints |
|---|---|---|
| case_version_id | TEXT | Primary Key |
| case_id | TEXT | Foreign Key |
| version_number | TEXT | Not Null |
| modality | TEXT | Not Null |
| language | TEXT | Not Null |
| schema_version | TEXT | Not Null |
| content_hash | TEXT | Optional |
| created_at | TEXT | Not Null |

Constraint:

- Unique combination of case_id and version_number.

Historical versions must remain accessible.

### 4.3 public_case_profiles

Stores authorized therapist-facing case introductions.

| Field | Type | Constraints |
|---|---|---|
| case_version_id | TEXT | Primary Key, Foreign Key |
| age | INTEGER | Optional |
| occupation | TEXT | Optional |
| presenting_concerns | TEXT | JSON |
| initial_disclosure | TEXT | Optional |
| profile_metadata | TEXT | JSON, Optional |
| created_at | TEXT | Not Null |

The application must display only information permitted by the scenario's disclosure configuration.

A public case profile must not contain restricted clinical formulation.

---

## 5. Simulation and Session Tables

### 5.1 simulation_runs

Represents one longitudinal execution of a synthetic case.

| Field | Type | Constraints |
|---|---|---|
| run_id | TEXT | Primary Key |
| case_id | TEXT | Foreign Key |
| case_version_id | TEXT | Foreign Key |
| modality | TEXT | Not Null |
| language | TEXT | Not Null |
| status | TEXT | Not Null |
| configuration_version | TEXT | Not Null |
| protocol_id | TEXT | Not Null |
| protocol_version | TEXT | Not Null |
| session_planning_policy | TEXT | Not Null |
| evaluation_rubric_id | TEXT | Not Null |
| evaluation_rubric_version | TEXT | Not Null |
| started_at | TEXT | Optional |
| completed_at | TEXT | Optional |
| created_at | TEXT | Not Null |

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

Each run must reference exactly one case version.
Run configuration fields are immutable after creation. The current supported
configuration is the flexible ACT educational simulation protocol
(`ACT_EDUCATIONAL_SIMULATION` 0.1) using `ACT_RUBRIC_V0` 0.2. This identifier
records simulation configuration; it is not a complete treatment manual.

### 5.2 sessions

Stores individual sessions belonging to a simulation run.

| Field | Type | Constraints |
|---|---|---|
| session_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_number | INTEGER | Not Null |
| status | TEXT | Not Null |
| transcript_version | INTEGER | Not Null, CHECK (transcript_version >= 1) |
| started_at | TEXT | Optional |
| ended_at | TEXT | Optional |
| created_at | TEXT | Not Null |

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

Constraints:

- Session number must be unique within a run.
- Session number must be a positive integer; there is no universal upper bound.

The application must enforce sequential session initialization without a fixed count.

Each subsequent session must not begin before the immediately preceding session reaches an allowed completed state.

The database constraints alone are not sufficient to enforce the complete workflow.

---

## 6. Conversation Tables

### 6.1 messages

Stores therapist-visible conversation messages.

| Field | Type | Constraints |
|---|---|---|
| message_id | TEXT | Primary Key |
| session_id | TEXT | Foreign Key |
| sequence_number | INTEGER | Not Null |
| role | TEXT | Not Null |
| content | TEXT | Not Null |
| model_run_id | TEXT | Foreign Key, Optional |
| content_hash | TEXT | Optional |
| created_at | TEXT | Not Null |

Allowed roles:

- therapist
- patient

Constraints:

- Sequence numbers must be unique within a session.
- Role must be restricted to the allowed values.

Internal prompts, agent reasoning, database credentials, and restricted context must not be stored as ordinary conversation messages.

### 6.2 Transcript Integrity

The transcript is reconstructed from messages ordered by sequence_number.

After session completion:

- Existing messages must not be silently modified.
- Corrections require an auditable versioned operation.
- The transcript version must be updated when an authorized correction changes its content.
- Evaluation reports must reference the exact transcript version used.

The original message content must remain recoverable.

---

## 7. Interaction Request and Idempotency

### 7.1 interaction_requests

Stores therapist message submission operations.

| Field | Type | Constraints |
|---|---|---|
| request_id | TEXT | Primary Key |
| session_id | TEXT | Foreign Key |
| idempotency_key | TEXT | Not Null |
| request_hash | TEXT | Not Null |
| therapist_message_id | TEXT | Foreign Key, Optional |
| patient_message_id | TEXT | Foreign Key, Optional |
| processing_status | TEXT | Not Null |
| error_code | TEXT | Optional |
| created_at | TEXT | Not Null |
| completed_at | TEXT | Optional |

Possible processing statuses:

- in_progress
- completed
- failed

### 7.2 Uniqueness

The combination of session_id and idempotency_key must be unique.

### 7.3 Idempotency Rules

When a request is repeated with the same key and identical request hash:

- A duplicate therapist message must not be created.
- A duplicate patient response must not be generated.
- The existing request status or result must be returned.

When a key is reused with a different request hash:

- The operation must be rejected.
- The API must return an idempotency conflict.

Failed requests must remain recorded.

A retry must follow an explicit recovery procedure and reuse the original operation identity.

The system must not assume that a timeout proves that the original model generation did not occur.

---

## 8. Disclosure Tracking Tables

Case fact content remains in the restricted database.

The operational database stores only disclosure metadata and supporting therapist-visible evidence references.

### 8.1 case_fact_disclosures

Stores the current disclosure status of a case fact within a simulation run.

| Field | Type | Constraints |
|---|---|---|
| disclosure_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| case_id | TEXT | Not Null |
| case_version_id | TEXT | Not Null |
| case_fact_id | TEXT | Not Null |
| disclosure_status | TEXT | Not Null |
| source_message_id | TEXT | Foreign Key, Optional |
| evidence_start_offset | INTEGER | Optional |
| evidence_end_offset | INTEGER | Optional |
| validation_method | TEXT | Not Null |
| validation_notes | TEXT | Optional |
| created_at | TEXT | Not Null |
| updated_at | TEXT | Not Null |

Possible disclosure statuses:

- not_disclosed
- candidate_disclosed
- confirmed_disclosed
- requires_review

Constraint:

- Unique combination of run_id and case_fact_id.

`case_fact_id` does not use a database foreign key because its definition is stored in the separate restricted database.

The application must validate the referenced case fact and case version.

### 8.2 case_fact_disclosure_history

Stores historical changes to disclosure status.

| Field | Type | Constraints |
|---|---|---|
| history_id | TEXT | Primary Key |
| disclosure_id | TEXT | Foreign Key |
| previous_status | TEXT | Optional |
| new_status | TEXT | Not Null |
| source_message_id | TEXT | Foreign Key, Optional |
| evidence_description | TEXT | Optional |
| operation_id | TEXT | Unique, Not Null |
| created_at | TEXT | Not Null |

Every disclosure status change must produce a history record.

The current disclosure status is stored in case_fact_disclosures.

Historical status changes must remain available.

### 8.3 Disclosure Validation

A candidate disclosure may be produced by the Patient Agent through an internal annotation.

The backend must verify:

- The case fact exists in the restricted case database.
- The case fact belongs to the same case version.
- The referenced message exists.
- The message belongs to the correct session.
- The source message is a patient message.
- The evidence span is valid.
- The disclosure policy permits the relevant disclosure.

An annotation alone must not establish confirmed disclosure.

---

# PART II — RESTRICTED CASE DATABASE

## 9. Restricted Case Tables

### 9.1 restricted_case_profiles

**Database:** `case_vault.db`

Stores restricted case definitions.

| Field | Type | Constraints |
|---|---|---|
| restricted_profile_id | TEXT | Primary Key |
| case_id | TEXT | Not Null |
| case_version_id | TEXT | Unique, Not Null |
| clinical_formulation | TEXT | JSON |
| relevant_personal_history | TEXT | JSON |
| maintaining_factors | TEXT | JSON |
| avoidance_patterns | TEXT | JSON |
| hypothesized_functions | TEXT | JSON |
| initial_safety_baseline | TEXT | JSON |
| patient_simulation_instructions | TEXT | Optional |
| created_at | TEXT | Not Null |

The referenced case version must exist in the operational database.

This relationship must be checked by the Patient Context Service.

### 9.2 case_facts

Stores individually identifiable fictional case information items.

| Field | Type | Constraints |
|---|---|---|
| case_fact_id | TEXT | Primary Key |
| case_id | TEXT | Not Null |
| case_version_id | TEXT | Not Null |
| fact_category | TEXT | Not Null |
| information_class | TEXT | Not Null |
| content | TEXT | Not Null |
| disclosure_policy | TEXT | Not Null |
| relevance_metadata | TEXT | JSON, Optional |
| created_at | TEXT | Not Null |

Example identifiers:

- AVA-FACT-001
- AVA-FACT-002
- AVA-FACT-003

Possible information classes:

- established_fact
- case_hypothesis
- unspecified_information

Possible disclosure policies:

- initial_disclosure
- contextually_disclosable
- restricted
- not_applicable

Constraint:

- The combination of case_id, case_version_id, and case_fact_id must be unique.

The application must ensure that every fact belongs to a valid restricted case profile.

### 9.3 Database Access

The Patient Context Service is the only authorized access path for constructing PatientContext.

The Patient Agent receives an explicitly constructed context object rather than an unrestricted database connection.

The Evaluator Agent must never receive this database connection.

---

# PART III — EVENT AND STATE MANAGEMENT

## 10. Event Tables

### 10.1 events

Stores operational and behavioral events.

| Field | Type | Constraints |
|---|---|---|
| event_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key, Optional |
| sequence_number | INTEGER | Not Null |
| event_type | TEXT | Not Null |
| actor | TEXT | Not Null |
| payload | TEXT | JSON |
| extraction_method | TEXT | Not Null |
| extractor_version | TEXT | Optional |
| event_status | TEXT | Not Null |
| idempotency_key | TEXT | Not Null |
| created_at | TEXT | Not Null |
| validated_at | TEXT | Optional |

Possible extraction methods:

- application_rule
- model_assisted
- manual

Possible event statuses:

- candidate
- accepted
- rejected
- requires_review

The combination of run_id and idempotency_key must be unique.

Deterministic application events may be accepted directly through validated backend operations.

Behavioral events must remain candidates until validated.

Extracted events remain `requires_review` until explicitly accepted or
rejected. Migration `012_event_review_history` adds the append-only review
record, and a database trigger prevents status changes without a matching
decision.

### 10.2 event_evidence

Links events to transcript messages.

| Field | Type | Constraints |
|---|---|---|
| event_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| evidence_type | TEXT | Not Null |
| start_offset | INTEGER | Optional |
| end_offset | INTEGER | Optional |
| annotation | TEXT | Optional |

Composite primary key:

- event_id
- message_id
- evidence_type

The application must verify that the referenced message belongs to the same session as the event.

Evidence offsets must follow a consistent character-indexing convention.

### 10.3 event_reviews

Stores one immutable decision for a behavioral event.

| Field | Type | Constraints |
|---|---|---|
| review_id | TEXT | Primary Key |
| event_id | TEXT | Unique Foreign Key |
| run_id | TEXT | Foreign Key paired with event_id |
| decision | TEXT | `accepted` or `rejected` |
| reviewer_id | TEXT | Not Null; authenticated local reviewer account ID |
| rationale | TEXT | Not Null |
| reviewed_at | TEXT | Not Null |

Review rows cannot be updated or deleted. A decision does not rewrite the
event's extracted description or evidence.

---

## 11. Clinical State Tables

### 11.1 state_snapshots

Stores immutable state snapshots.

| Field | Type | Constraints |
|---|---|---|
| snapshot_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key, Optional |
| previous_snapshot_id | TEXT | Self-referencing Foreign Key, Optional |
| state_schema_version | TEXT | Not Null |
| snapshot_reason | TEXT | Not Null |
| created_at | TEXT | Not Null |

The initial state snapshot must be created before the first simulated interaction.

### 11.2 state_snapshot_values

Stores individual variable values.

| Field | Type | Constraints |
|---|---|---|
| snapshot_id | TEXT | Foreign Key |
| variable_name | TEXT | Not Null |
| variable_value | INTEGER | Not Null |

Composite primary key:

- snapshot_id
- variable_name

Allowed variables:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Constraint:

- Every initial variable value must be between 0 and 4.

The application must also validate the permitted variable names.

### 11.3 state_transitions

Stores proposed and validated state transitions.

| Field | Type | Constraints |
|---|---|---|
| transition_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key |
| event_id | TEXT | Foreign Key, Optional |
| variable_name | TEXT | Not Null |
| previous_value | INTEGER | Not Null |
| proposed_value | INTEGER | Not Null |
| accepted_value | INTEGER | Optional |
| validation_status | TEXT | Not Null |
| transition_rule_id | TEXT | Optional |
| transition_rule_version | TEXT | Optional |
| resulting_snapshot_id | TEXT | Foreign Key, Optional |
| confidence | TEXT | Optional |
| uncertainty_notes | TEXT | Optional |
| idempotency_key | TEXT | Not Null |
| created_at | TEXT | Not Null |
| validated_at | TEXT | Optional |

Possible validation statuses:

- pending
- accepted
- rejected
- requires_review

Constraints:

- Values must be within the allowed range.
- Accepted value must be populated only after successful validation.
- Rejected transitions must remain stored.
- The combination of run_id and idempotency_key must be unique.

The LLM must not write directly to state_snapshots or state_snapshot_values.

### 11.4 transition_evidence

Links proposed transitions to supporting messages.

| Field | Type | Constraints |
|---|---|---|
| transition_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| evidence_role | TEXT | Not Null |
| relevance_note | TEXT | Optional |

Composite primary key:

- transition_id
- message_id

Messages must belong to the relevant simulation run.

The State Engine remains responsible for validating the evidence.

---

## 12. Longitudinal Memory Tables

### 12.1 memory_items

Stores selected information retained between sessions.

| Field | Type | Constraints |
|---|---|---|
| memory_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| source_session_id | TEXT | Foreign Key, Optional |
| memory_type | TEXT | Not Null |
| information_class | TEXT | Not Null |
| content | TEXT | Not Null |
| confidence | REAL | Optional |
| status | TEXT | Not Null |
| memory_version | INTEGER | Not Null |
| memory_scope | TEXT | Not Null |
| supersedes_memory_id | TEXT | Optional self-reference |
| origin_interaction_request_id | TEXT | Optional Foreign Key |
| proposal_index | INTEGER | Optional, non-negative |
| created_at | TEXT | Not Null |
| updated_at | TEXT | Not Null |

Allowed information classes:

- confirmed_fact
- explicit_disclosure
- therapist_hypothesis
- system_generated_summary
- reported_outcome
- structured_observation

Possible statuses:

- active
- superseded
- requires_review
- rejected

The confidence field represents system uncertainty, not a validated psychological probability.

### 12.2 memory_evidence

Links memory items to original messages.

| Field | Type | Constraints |
|---|---|---|
| memory_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| relationship_type | TEXT | Not Null |
| start_offset | INTEGER | Optional, Unicode code-point offset |
| end_offset | INTEGER | Optional, Unicode code-point offset |

Composite primary key:

- memory_id
- message_id

Memory updates must preserve historical versions and source references.

The original transcript remains the authoritative record.

### 12.3 memory_reviews

Stores one immutable acceptance or rejection decision for a candidate, including the reviewer identifier, rationale, and review timestamp. Accepted and rejected memory records remain in `memory_items`; only `active` records may be retrieved as patient memory.

### 12.4 memory_consolidation_sources

Migration 015 records immutable links from a proposed consolidated memory to
each original memory, including a snapshot of its version, session, and
content, and whether the deterministic text heuristic found the pair related,
repeated, or potentially contradictory. Transcript evidence is copied as
references to the original message IDs; source memory records are never
overwritten. Consolidated records are created as `requires_review` and cannot
affect patient context until explicitly accepted.

### 12.5 memory_extraction_jobs

Durable post-interaction outbox for optional model-assisted memory proposal generation.

| Field | Type | Constraints |
|---|---|---|
| job_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key scoped to Run |
| interaction_request_id | TEXT | Unique Foreign Key |
| status | TEXT | `pending`, `processing`, `completed`, or `failed` |
| attempt_count | INTEGER | Non-negative |
| candidate_count | INTEGER | Non-negative |
| available_at | TEXT | Not Null; retry scheduling |
| lease_owner | TEXT | Required only while processing |
| lease_expires_at | TEXT | Required only while processing |
| proposal_payload | TEXT | Optional validated, versioned output for replay |
| output_hash | TEXT | Optional SHA-256 of proposal payload |
| character_state_snapshot_id | TEXT | Optional FK to the Run character-state snapshot captured when the interaction was enqueued |
| last_error_code | TEXT | Optional sanitized error code |
| created_at / updated_at | TEXT | Not Null |
| completed_at | TEXT | Required only when completed |

The outbox row is created in the same transaction that completes an interaction and records its deterministic events. Model execution occurs after that transaction. Leases recover abandoned work, retries are bounded, and saved structured output makes candidate persistence safely replayable without calling the model again.

Migration `011_memory_extraction_state_context` adds the nullable
`character_state_snapshot_id` and an index. Workers use this pinned snapshot,
not the Run's latest state, when constructing delayed extraction context.
Legacy jobs with a null reference remain processable for memory and event
proposals, but cannot submit state-transition proposals.

### 12.6 treatment_plan_revisions

Stores immutable, versioned plan snapshots for a Run.

| Field | Type | Constraints |
|---|---|---|
| revision_id | TEXT | Primary Key |
| plan_id | TEXT | Stable identifier across revisions |
| run_id | TEXT | Foreign Key |
| revision_number | INTEGER | Positive; unique within Run |
| based_on_revision_number | INTEGER | Active revision number used as the proposal base; null for initial plan |
| modality | TEXT | Copied from Run |
| protocol_id / protocol_version | TEXT | Pinned protocol identity |
| plan_json | TEXT | Validated goals, objectives, interventions, measures, review point, evidence, and rationale |
| status | TEXT | `active`, `requires_review`, `superseded`, or `rejected` |
| created_at | TEXT | Not Null |

Revision content is immutable. A Run can have at most one active revision and
one pending proposal. The initial plan is an explicitly authored baseline;
later proposals must cite same-Run evidence. Only accepted events, accepted
state transitions, completed sessions, and same-Run evaluations can be cited
by the current service.

### 12.7 treatment_plan_reviews

Stores one immutable decision for a proposed plan revision.

| Field | Type | Constraints |
|---|---|---|
| review_id | TEXT | Primary Key |
| revision_id | TEXT | Unique Foreign Key |
| run_id | TEXT | Paired Foreign Key |
| decision | TEXT | `accepted` or `rejected` |
| reviewer_id | TEXT | Authenticated local reviewer account ID |
| rationale | TEXT | Not Null |
| reviewed_at | TEXT | Not Null |

Acceptance atomically supersedes the prior active revision and activates the
proposal. Rejection leaves the active revision unchanged. This is a
human-proposed workflow; automatic progress inference and plan adaptation are
not implemented.

---

# PART IV — EVALUATION

## 13. Rubric Tables

### 13.1 rubric_versions

Stores versioned therapeutic evaluation rubrics.

| Field | Type | Constraints |
|---|---|---|
| rubric_version_id | TEXT | Primary Key |
| rubric_id | TEXT | Not Null |
| version_number | TEXT | Not Null |
| modality | TEXT | Not Null |
| language | TEXT | Not Null |
| schema_version | TEXT | Not Null |
| rubric_definition | TEXT | JSON |
| content_hash | TEXT | Optional |
| created_at | TEXT | Not Null |

Constraint:

- Unique combination of rubric_id and version_number.

Historical rubric versions must remain available.

---

## 14. Evaluation Tables

### 14.1 evaluations

Stores both session-level and longitudinal evaluation reports.

| Field | Type | Constraints |
|---|---|---|
| evaluation_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key, Optional |
| evaluation_scope | TEXT | Not Null |
| rubric_version_id | TEXT | Foreign Key |
| transcript_manifest | TEXT | JSON |
| evaluator_model_run_id | TEXT | Foreign Key, Optional |
| overall_summary | TEXT | Optional |
| report_metadata | TEXT | JSON, Optional; includes evaluator provenance and scope metadata |
| evaluation_revision | INTEGER | Not Null |
| status | TEXT | Not Null |
| created_at | TEXT | Not Null |

Allowed evaluation scopes:

- session
- longitudinal

Possible statuses:

- pending
- completed
- failed
- requires_review

Constraints:

- Session-level evaluation requires a non-null session_id.
- Longitudinal evaluation requires a null session_id.
- Every evaluation must reference a valid run_id.
- Every evaluation must reference a specific rubric version.

The application must verify that all transcript references belong to the same run and case version.

### 14.2 Evaluation Scope Rules

**Session-level evaluation:**

- References exactly one completed session.
- Uses the finalized transcript version for that session.
- Produces competency-specific results.

**Longitudinal evaluation:**

- References the entire simulation run.
- Uses every completed session transcript in the Run; at least two completed
  sessions are required.
- Captures a snapshot of all Run sessions, including in-progress sessions, so
  later session creation or status changes can invalidate the report.
- Preserves chronological order.
- Evaluates therapeutic continuity and adaptation across sessions.

The application stores the completed transcript manifest and hashes, the
evaluated session IDs/numbers/hashes, and the Run-session ID/number/status
snapshot in `report_metadata`. A report is stale if the Run-session snapshot
changes or any included completed transcript hash changes. Older longitudinal
records without a Run-session snapshot are treated as stale.

### 14.3 evaluation_items

Stores individual competency results.

| Field | Type | Constraints |
|---|---|---|
| evaluation_item_id | TEXT | Primary Key |
| evaluation_id | TEXT | Foreign Key |
| competency_id | TEXT | Not Null |
| rating_code | TEXT | Not Null |
| justification | TEXT | Optional |
| alternative_response | TEXT | Optional |
| limitations | TEXT | Optional |
| uncertainty_notes | TEXT | Optional |

Allowed rating values:

- 0
- 1
- 2
- 3
- NE

The permitted competency identifiers must come from the referenced rubric version.

### 14.4 evaluation_evidence

Links competency results to transcript evidence.

| Field | Type | Constraints |
|---|---|---|
| evaluation_item_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| evidence_role | TEXT | Not Null |
| start_offset | INTEGER | Optional |
| end_offset | INTEGER | Optional |
| evidence_excerpt | TEXT | Optional |
| evidence_note | TEXT | Optional |

Composite primary key:

- evaluation_item_id
- message_id
- evidence_role

All referenced messages must belong to the evaluated session or to one of the sessions included in the longitudinal evaluation.

The application must verify this condition.

### 14.5 evaluation_reviews

Stores authenticated, append-only reviewer feedback without modifying the
generated evaluation revision.

| Field | Type | Constraints |
|---|---|---|
| review_id | TEXT | Primary Key |
| evaluation_id | TEXT | Foreign Key |
| review_number | INTEGER | Positive; unique per evaluation |
| reviewer_user_id | TEXT | Foreign Key to local reviewer account |
| decision | TEXT | `accepted` or `revision_requested` |
| feedback | TEXT | Required; 1–4000 characters |
| created_at | TEXT | Not Null |

Database triggers reject updates and deletes. Migration
`017_evaluation_reviews` adds this table without rewriting existing reports.

---

## 15. Model Execution Table

### 15.1 model_runs

Stores metadata for every language-model execution.

| Field | Type | Constraints |
|---|---|---|
| model_run_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key, Optional |
| session_id | TEXT | Foreign Key, Optional |
| component | TEXT | Not Null |
| provider | TEXT | Not Null |
| model_identifier | TEXT | Not Null |
| model_version | TEXT | Optional |
| model_artifact_digest | TEXT | Optional |
| prompt_id | TEXT | Optional |
| prompt_version | TEXT | Optional |
| input_schema_version | TEXT | Optional |
| output_schema_version | TEXT | Optional |
| generation_parameters | TEXT | JSON |
| input_hash | TEXT | Optional |
| output_hash | TEXT | Optional |
| random_seed | INTEGER | Optional |
| execution_status | TEXT | Not Null |
| output_validation_status | TEXT | Optional |
| started_at | TEXT | Not Null |
| completed_at | TEXT | Optional |

Supported components:

- patient_agent
- evaluator_agent
- memory_extraction_agent (optional secondary execution)

Deterministic event processing and memory validation do not create model-run
records; only the optional MemoryExtractionAgent execution does.

---

## 16. Audit Table

### 16.1 audit_events

Stores security and operational events.

| Field | Type | Constraints |
|---|---|---|
| audit_event_id | TEXT | Primary Key |
| component | TEXT | Not Null |
| operation_type | TEXT | Not Null |
| entity_type | TEXT | Not Null |
| entity_id | TEXT | Optional |
| run_id | TEXT | Optional |
| session_id | TEXT | Optional |
| operation_status | TEXT | Not Null |
| metadata | TEXT | JSON, Optional |
| created_at | TEXT | Not Null |

Examples:

- simulation_run_created
- session_started
- message_persisted
- interaction_failed
- patient_context_retrieved
- disclosure_candidate_created
- disclosure_confirmed
- event_accepted
- event_rejected
- event_reviewed
- state_transition_accepted
- state_transition_rejected
- evaluation_generated
- evaluation_failed
- memory_updated

Audit records must avoid unnecessary duplication of restricted content.

---

# PART V — DATA INTEGRITY

## 17. Referential Integrity

All relationships within the operational database must use valid foreign keys.

The following relationships must be enforced:

- case_versions to cases.
- public_case_profiles to case_versions.
- simulation_runs to cases and case_versions.
- sessions to simulation_runs.
- messages to sessions.
- interaction_requests to sessions and messages.
- events to simulation_runs and sessions.
- event_evidence to events and messages.
- event_reviews to events and Runs.
- case_fact_disclosures to runs and evidence messages.
- case_fact_disclosure_history to disclosure records.
- state_snapshots to simulation_runs and sessions.
- state_snapshot_values to state_snapshots.
- state_transitions to runs, sessions, and snapshots.
- transition_evidence to transitions and messages.
- memory_items to runs and sessions.
- memory_evidence to memory items and messages.
- evaluations to runs, sessions, and rubric versions.
- evaluation_items to evaluations.
- evaluation_evidence to evaluation items and messages.
- evaluation_reviews to evaluations and authenticated local reviewers.
- model_runs to their associated run and session where applicable.

Cross-database relationships must be verified by application services.

---

## 18. Transaction and Consistency Rules

Operations involving multiple database writes must use transactions.

### 18.1 Interaction Processing

The interaction workflow must:

1. Validate the session.
2. Validate the idempotency key and request hash.
3. Persist the InteractionRequest.
4. Persist the therapist message exactly once.
5. Execute Patient Agent generation.
6. Validate the PatientResponse.
7. Persist the patient response.
8. Update interaction status.
9. Persist deterministic operational events.
10. Commit the corresponding database operations.

Where model generation happens outside the database transaction, the request record must preserve its intermediate status.

The system must not hold a long-running SQLite write transaction open while waiting for model generation.

If generation fails:

- Preserve the therapist message.
- Record the failure.
- Keep the request recoverable.
- Do not fabricate a patient response.
- Do not modify clinical state as a result of the failed generation.

### 18.2 State Update Transaction

An accepted state transition should:

1. Validate the transition proposal.
2. Begin a database transaction.
3. Insert the transition record.
4. Create the new state snapshot.
5. Insert its variable values.
6. Link the transition to the snapshot.
7. Record the audit event.
8. Commit the transaction.

If any required database operation fails, the transaction must be rolled back.

### 18.3 Disclosure Update

A validated disclosure update must:

1. Verify the case fact reference against the restricted database.
2. Validate the patient message reference.
3. Validate the evidence span.
4. Begin an operational database transaction.
5. Update the current disclosure status.
6. Insert the disclosure history record.
7. Insert the corresponding audit event.
8. Commit the transaction.

### 18.4 Evaluation Completion

Evaluation generation must be independent of session completion.

The system must:

- Preserve completed sessions.
- Store the evaluation request.
- Record model execution.
- Validate report structure.
- Persist evaluation and competency results transactionally.
- Keep failed evaluations marked as failed.

A failed evaluation must not invalidate the completed simulation session.

---

## 19. Idempotency Rules

The database must support safe repeated requests.

Initial protected operations:

- Therapist message submission.
- Session creation.
- Evaluation generation.
- Event processing.
- State transition acceptance.
- Disclosure status updates.

Each operation must have a stable idempotency identity.

Repeated operations must not create duplicate accepted results.

A repeated operation with conflicting input must return an explicit error.

---

## 20. Indexing Strategy

Recommended indexes:

- case_versions.case_id
- simulation_runs.case_id
- simulation_runs.case_version_id
- sessions.run_id
- messages.session_id
- messages.session_id + sequence_number
- interaction_requests.session_id + idempotency_key
- events.run_id
- events.session_id
- events.event_type
- case_fact_disclosures.run_id + case_fact_id
- case_fact_disclosure_history.disclosure_id
- state_snapshots.run_id
- state_transitions.run_id
- state_transitions.session_id
- memory_items.run_id
- evaluations.run_id
- evaluations.session_id
- evaluation_items.evaluation_id
- model_runs.session_id

Unique constraints and indexes must be validated against actual queries during implementation.

---

## 21. Database Access Boundaries

| Component | Operational Database | Restricted Database |
|---|---|---|
| Therapist Interface | Authorized API data only | No access |
| Patient Context Service | Authorized operational data | Authorized read |
| Patient Agent | Explicit PatientContext | No direct connection |
| Evaluator Agent | Explicit EvaluationInput | No access |
| Event Processing Service | Authorized transcripts and events | No direct access |
| Clinical State Engine | State, events, and evidence | No direct access |
| Memory Service | Authorized memory and transcript data | No direct access |
| Orchestrator | Controlled repository interfaces | No unrestricted access |

The Evaluator Agent must not receive an unrestricted database session or repository object.

The Patient Agent must receive an explicitly constructed context object.

The architecture is a local single-user prototype, not a complete security boundary against a local administrator.

---

## 22. Backup and Recovery

The initial application must support:

- Operational database backup.
- Restricted database backup.
- Consistent backup metadata.
- Restoration validation.
- Historical session recovery.
- Case version preservation.
- Rubric version preservation.
- Transcript integrity checks.

When backing up both databases, the application must record their corresponding backup set and timestamp.

Backups must preserve the association between case versions and simulation runs.

Restricted case information must remain subject to access restrictions in backups.

---

## 23. Migration Strategy

Database schema changes must be versioned.

The implementation will maintain a migration history table.

Proposed table:

`schema_migrations`

Fields:

- migration_id
- version
- description
- applied_at
- checksum

Migration rules:

1. Every schema change must have a version identifier.
2. Migrations must be repeatable in controlled test environments.
3. Historical data must not be silently reinterpreted.
4. Destructive migrations require an explicit backup and recovery plan.
5. Operational and restricted databases must track their migration versions independently.

The migration tool and repository technology will be selected during implementation.

---

## 24. Data Retention

The initial MVP uses synthetic case information only.

The system must preserve completed simulation records for reproducibility unless an explicit deletion policy is implemented.

Any deletion or correction must be an auditable operation where appropriate.

The system must not silently delete:

- Historical transcripts.
- Accepted transitions.
- Rejected transition records.
- Historical memory versions.
- Evaluation reports.
- Model execution metadata needed for reproducibility.

---

## 25. Initial MVP Table Inventory

### Operational Database: therasim.db

Required tables:

1. cases
2. case_versions
3. public_case_profiles
4. simulation_runs
5. sessions
6. messages
7. interaction_requests
8. case_fact_disclosures
9. case_fact_disclosure_history
10. events
11. event_evidence
12. event_reviews
13. state_snapshots
14. state_snapshot_values
15. state_transitions
16. transition_evidence
17. memory_items
18. memory_evidence
19. memory_reviews
20. rubric_versions
21. evaluations
22. evaluation_items
23. evaluation_evidence
24. model_runs
25. audit_events
26. memory_extraction_jobs
27. treatment_plan_revisions
28. treatment_plan_reviews
29. schema_migrations
30. local_auth_users
31. local_auth_sessions
32. local_auth_login_attempts
33. evaluation_reviews

### Restricted Database: case_vault.db

Required tables:

1. restricted_case_profiles
2. case_facts
3. schema_migrations

---

## 25.1 Local Authentication Tables (Migration 014)

`local_auth_users` stores the single local reviewer account:

- `user_id`: fixed local account identity, `local-reviewer`.
- `reviewer_name`: display name supplied during first-run setup.
- `password_hash`: scrypt hash with per-user random salt and fixed parameters.
- `created_at`: account creation timestamp.

`local_auth_sessions` stores bearer-session metadata:

- `session_id`: opaque internal session identifier.
- `user_id`: foreign key to the local reviewer.
- `token_sha256`: hash of the bearer token; the raw token is not persisted.
- `created_at`, `expires_at`, and optional `revoked_at`.

Sessions expire after eight hours. Expired and revoked sessions may be removed
when a new login is created. The operational database and backups contain
password hashes and session metadata and must be kept private.

---

## 26. Important Implementation Notes

1. Every table must have explicit primary-key and nullability definitions.
2. JSON fields must be schema-validated by the application.
3. Cross-database foreign keys must be validated manually.
4. Operational and restricted databases must have separate connection interfaces.
5. Evaluator Agent must never receive a restricted database connection.
6. Patient Agent must receive only explicit PatientContext.
7. Session transcripts must remain immutable after completion.
8. Historical state snapshots must remain recoverable.
9. Evaluation scope must distinguish session and longitudinal reports.
10. Interaction idempotency must be enforced through database constraints and application logic.
11. Disclosure history must remain traceable.
12. Model and prompt versions must be recorded.
13. Database writes involving related records must use transactions.
14. Security boundaries must be tested independently from logical schema separation.

---

## 27. Open Implementation Questions

The following decisions remain for the implementation phase:

- Which database access library should be used?
- Should repository operations use raw SQL or an ORM?
- Which migration implementation best fits the modular monolith?
- Should database backups use SQLite's online backup API?
- Should restricted database files receive additional Windows ACL protection?
- How should concurrent local requests be serialized?
- Should large transcripts be paginated or retrieved as complete session objects?
- Which JSON fields need dedicated indexing?

These decisions must be resolved during implementation without changing the established data contracts unnecessarily.

---

**End of Document**

<!-- CHARACTER_DATABASE_SCHEMA_NOTE_V0_1 -->
## Character-centered persistence extension

See `CHARACTER_MODEL_SPEC.md` for the canonical schema design.

### Restricted database

The planned `character_personality_profiles` table stores one immutable,
versioned personality definition for an exact case version. It belongs in
the restricted database because it may contain private hypotheses and
internal character guidance.

### Operational database

The existing `events`, `event_evidence`, `memory_items`, `memory_evidence`,
and ACT state tables remain the foundation for run-specific history.

The planned generic character-state persistence consists of:

- `character_state_snapshots`
- `character_state_snapshot_values`
- `character_state_transitions`
- `character_state_transition_evidence`

These structures must remain distinct from the existing ACT process-state
tables.

No character-model migration has been applied by this documentation change.
The proposed schema must be introduced using the existing checksum-verified
migration mechanism.
