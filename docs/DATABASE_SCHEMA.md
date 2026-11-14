# TheraSim — Database Schema

**Document Version:** 0.1
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the logical database schema for TheraSim.

The initial implementation will use SQLite for persistent storage of:

- Synthetic case metadata.
- Case versions.
- Longitudinal simulation runs.
- Individual psychotherapy sessions.
- Therapist and patient messages.
- Interaction events.
- Clinical state snapshots.
- State transition records.
- Longitudinal memory.
- Therapeutic evaluation reports.
- Model execution metadata.
- Audit records.

The schema is designed to support reproducibility, data integrity, longitudinal consistency, and controlled access to sensitive synthetic case information.

This document defines the logical database design. Exact SQL statements, indexes, migrations, and Pydantic models will be specified during implementation.

---

## 2. Database Architecture

The preferred initial architecture separates operational simulation data from restricted synthetic case information.

### 2.1 Operational Database

**File:** `therasim.db`

Contains:

- Case metadata and public profiles.
- Simulation runs.
- Session records.
- Conversation messages.
- Events and evidence references.
- Clinical state snapshots.
- State transitions.
- Longitudinal memory.
- Rubric versions.
- Evaluation reports.
- Model execution metadata.
- Audit records.

### 2.2 Restricted Case Database

**File:** `case_vault.db`

Contains:

- Restricted clinical formulations.
- Undisclosed personal history.
- Maintaining-factor hypotheses.
- Hidden behavioral patterns.
- Restricted case information.
- Internal case-specific simulation instructions.

The restricted database is accessible only through an authorized Patient Context component.

The Evaluator Agent must never receive a database connection or unrestricted repository access to this database.

### 2.3 Access Separation

The separation between the two databases is intended to reduce accidental information leakage.

The application must also enforce access restrictions through repository interfaces, service boundaries, and explicit data-transfer objects.

SQLite does not provide built-in row-level access control. Separate database files alone are not a complete security boundary, particularly when all components execute within the same operating-system process.

Stronger isolation may be introduced through separate processes and restricted operating-system permissions in later versions.

---

## 3. Database Conventions

The following conventions apply to all tables.

### 3.1 Identifiers

- Primary keys use UUID strings.
- Foreign keys reference the associated record identifiers.
- Identifiers must remain stable across the lifetime of a record.

### 3.2 Timestamps

All timestamps must:

- Use UTC.
- Be stored in a consistent ISO 8601 representation.
- Include timezone information.
- Avoid dependence on the local computer's timezone.

### 3.3 Structured Data

SQLite does not require a dedicated JSON column type for this design.

Structured objects may be stored as JSON-serialized TEXT values.

The application must validate these values before insertion and after retrieval.

Examples include:

- Model configuration.
- Event payloads.
- Case formulation structures.
- Evaluation metadata.

### 3.4 Data Integrity

The implementation must enable:

- Foreign key enforcement.
- Explicit CHECK constraints.
- Unique constraints where required.
- Transactional state updates.
- Validated references between related records.

The application must execute `PRAGMA foreign_keys = ON` for every SQLite connection.

---

## 4. Entity Relationship Overview

The main operational database contains the following logical relationships:

- One case may have multiple case versions.
- One case version may have multiple simulation runs.
- One simulation run contains multiple sessions.
- One session contains multiple messages.
- One session may generate multiple events.
- An event may reference multiple transcript messages.
- One simulation run may contain multiple state snapshots.
- A state snapshot contains multiple variable values.
- A transition may reference supporting evidence.
- One simulation run may contain multiple memory items.
- One session may have multiple evaluation records.
- One evaluation contains multiple competency results.
- A model execution may be associated with a session or an internal component operation.

The restricted case database references the corresponding case version through its identifier.

---

## 5. Main Database Tables

### 5.1 cases

Stores the identity and general metadata of a synthetic case.

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

This table must not contain restricted clinical formulation information.

### 5.2 case_versions

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

- A case must not contain duplicate version numbers.

Previous case versions must remain available when a case is modified.

### 5.3 public_case_profiles

Stores the information that may be used to introduce the synthetic client.

| Field | Type | Constraints |
|---|---|---|
| case_version_id | TEXT | Primary Key, Foreign Key |
| age | INTEGER | Optional |
| occupation | TEXT | Optional |
| presenting_concerns | TEXT | JSON |
| initial_disclosure | TEXT | Optional |
| profile_metadata | TEXT | JSON, Optional |

This information is not automatically visible to the therapist in full. The Therapist Interface must display only the content authorized for the simulation.

---

## 6. Restricted Case Database

### 6.1 restricted_case_profiles

**Database:** `case_vault.db`

Stores the confidential simulation definition required by the Patient Agent.

| Field | Type | Constraints |
|---|---|---|
| restricted_profile_id | TEXT | Primary Key |
| case_version_id | TEXT | Not Null, Unique |
| clinical_formulation | TEXT | JSON |
| relevant_personal_history | TEXT | JSON |
| maintaining_factors | TEXT | JSON |
| avoidance_patterns | TEXT | JSON |
| hypothesized_functions | TEXT | JSON |
| undisclosed_information | TEXT | JSON |
| initial_safety_baseline | TEXT | JSON |
| patient_simulation_instructions | TEXT | Optional |
| created_at | TEXT | Not Null |

The application must validate that the referenced case version exists in the operational database.

This reference is maintained at the application level because SQLite foreign keys cannot enforce relationships across separate database files.

### Access Restrictions

- Patient Context component: authorized read access.
- Patient Agent: receives only the required context.
- Evaluator Agent: no access.
- Therapist Interface: no direct access.
- State Engine: no direct access unless an explicitly authorized rule requires a limited input.
- Orchestrator: coordinates access but should not expose restricted content to unrelated components.

---

## 7. Simulation and Session Tables

### 7.1 simulation_runs

Represents one longitudinal execution of a synthetic case.

A simulation run may contain several connected psychotherapy sessions.

| Field | Type | Constraints |
|---|---|---|
| run_id | TEXT | Primary Key |
| case_id | TEXT | Foreign Key |
| case_version_id | TEXT | Foreign Key |
| status | TEXT | Not Null |
| language | TEXT | Not Null |
| modality | TEXT | Not Null |
| configuration_hash | TEXT | Optional |
| started_at | TEXT | Not Null |
| completed_at | TEXT | Optional |
| created_at | TEXT | Not Null |

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

A simulation run must retain the exact case version used during execution.

### 7.2 sessions

Stores individual sessions belonging to a simulation run.

| Field | Type | Constraints |
|---|---|---|
| session_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_number | INTEGER | Not Null |
| status | TEXT | Not Null |
| started_at | TEXT | Optional |
| ended_at | TEXT | Optional |
| transcript_version | INTEGER | Not Null |
| created_at | TEXT | Not Null |

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

Constraint:

- Session numbers must be unique within the same simulation run.

---

## 8. Model Execution Table

### 8.1 model_runs

Stores metadata about language-model executions.

| Field | Type | Constraints |
|---|---|---|
| model_run_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key, Optional |
| session_id | TEXT | Foreign Key, Optional |
| component | TEXT | Not Null |
| provider | TEXT | Not Null |
| model_identifier | TEXT | Not Null |
| model_version | TEXT | Optional |
| prompt_version | TEXT | Optional |
| generation_parameters | TEXT | JSON |
| input_hash | TEXT | Optional |
| output_hash | TEXT | Optional |
| random_seed | INTEGER | Optional |
| execution_status | TEXT | Not Null |
| started_at | TEXT | Not Null |
| completed_at | TEXT | Optional |

Possible components:

- patient_agent
- evaluator_agent
- event_extractor
- memory_processor
- other

Possible execution statuses:

- started
- completed
- failed
- interrupted

Model metadata is required for reproducibility and comparison.

Hidden prompts and internal reasoning must not be exposed through ordinary session or evaluation records.

---

## 9. Conversation Tables

### 9.1 messages

Stores the chronological conversation.

| Field | Type | Constraints |
|---|---|---|
| message_id | TEXT | Primary Key |
| session_id | TEXT | Foreign Key |
| sequence_number | INTEGER | Not Null |
| role | TEXT | Not Null |
| content | TEXT | Not Null |
| model_run_id | TEXT | Foreign Key, Optional |
| visible_to_therapist | INTEGER | Not Null |
| created_at | TEXT | Not Null |

Allowed roles:

- therapist
- patient
- system

The sequence number must be unique within a session.

Message content must preserve the original interaction.

Internal agent reasoning, hidden prompts, and restricted case material must not be stored as ordinary therapist-visible messages.

### 9.2 Transcript Integrity

The transcript is reconstructed from messages ordered by sequence number.

After session completion:

- Existing messages must not be silently modified.
- Corrections must create an auditable record.
- The transcript version must be incremented when an authorized correction changes the transcript.
- Evaluation reports must reference the transcript version and preferably its content hash.

---

## 10. Event Tables

### 10.1 events

Stores structured interaction events.

| Field | Type | Constraints |
|---|---|---|
| event_id | TEXT | Primary Key |
| session_id | TEXT | Foreign Key |
| sequence_number | INTEGER | Not Null |
| event_type | TEXT | Not Null |
| actor | TEXT | Not Null |
| payload | TEXT | JSON |
| extraction_method | TEXT | Not Null |
| extractor_version | TEXT | Optional |
| event_status | TEXT | Not Null |
| idempotency_key | TEXT | Not Null |
| created_at | TEXT | Not Null |

Possible extraction methods:

- rule_based
- model_assisted
- manual

Possible event statuses:

- candidate
- accepted
- rejected
- requires_review

The combination of session ID and idempotency key must be unique.

### 10.2 event_evidence

Links events to exact transcript evidence.

| Field | Type | Constraints |
|---|---|---|
| event_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| start_offset | INTEGER | Optional |
| end_offset | INTEGER | Optional |
| evidence_type | TEXT | Not Null |
| annotation | TEXT | Optional |

Composite Primary Key:

- event_id
- message_id
- start_offset

Offsets must refer to the original message content using a consistent character-indexing convention.

The referenced message must belong to the same session as its event.

---

## 11. Clinical State Tables

### 11.1 state_snapshots

Stores historical snapshots of the structured simulation state.

| Field | Type | Constraints |
|---|---|---|
| snapshot_id | TEXT | Primary Key |
| run_id | TEXT | Foreign Key |
| session_id | TEXT | Foreign Key, Optional |
| previous_snapshot_id | TEXT | Self-referencing Foreign Key, Optional |
| state_schema_version | TEXT | Not Null |
| snapshot_reason | TEXT | Not Null |
| created_at | TEXT | Not Null |

The initial snapshot must be stored before the first simulated interaction.

A new snapshot must be created after accepted state changes or explicit checkpoints.

### 11.2 state_snapshot_values

Stores the individual variable values within each snapshot.

| Field | Type | Constraints |
|---|---|---|
| snapshot_id | TEXT | Foreign Key |
| variable_name | TEXT | Not Null |
| variable_value | INTEGER | Not Null |

Composite Primary Key:

- snapshot_id
- variable_name

Initial variables:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Constraint:

- The initial state variables must contain values from 0 to 4.

The application must validate the permitted variable names and their operational definitions.

---

## 12. State Transition Tables

### 12.1 state_transitions

Stores proposed and validated state changes.

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

- Previous and proposed values must be within the permitted range.
- Accepted value must remain within the permitted range.
- Accepted value must be populated only after successful validation.
- Transition idempotency keys must be unique within a session.

### 12.2 transition_evidence

Links a transition to its supporting messages.

| Field | Type | Constraints |
|---|---|---|
| transition_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| evidence_role | TEXT | Not Null |
| relevance_note | TEXT | Optional |

Composite Primary Key:

- transition_id
- message_id

The implementation must verify that the referenced messages belong to the same simulation run and relevant session.

Rejected transitions must remain stored for audit and debugging purposes.

---

## 13. Longitudinal Memory Tables

### 13.1 memory_items

Stores structured memory across sessions.

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
| created_at | TEXT | Not Null |
| updated_at | TEXT | Not Null |

Possible information classes:

- disclosed_fact
- therapist_hypothesis
- system_generated_summary
- reported_outcome
- structured_observation

Possible statuses:

- active
- superseded
- requires_review

Confidence must represent system uncertainty and must not be described as a validated psychological probability.

Memory items must retain their information class and source references.

### 13.2 memory_evidence

Links memory records to their supporting evidence.

| Field | Type | Constraints |
|---|---|---|
| memory_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| relationship_type | TEXT | Not Null |

Composite Primary Key:

- memory_id
- message_id

A memory record must not be presented as a directly disclosed fact when it originated from a system-generated interpretation.

---

## 14. Evaluation Tables

### 14.1 rubric_versions

Stores versioned evaluation rubrics.

| Field | Type | Constraints |
|---|---|---|
| rubric_version_id | TEXT | Primary Key |
| rubric_id | TEXT | Not Null |
| version_number | TEXT | Not Null |
| modality | TEXT | Not Null |
| language | TEXT | Not Null |
| schema_version | TEXT | Not Null |
| rubric_definition | TEXT | JSON |
| created_at | TEXT | Not Null |

Constraint:

- Rubric ID and version number must form a unique pair.

Previously used rubric versions must remain available for historical evaluations.

### 14.2 evaluations

Stores the overall evaluation report.

| Field | Type | Constraints |
|---|---|---|
| evaluation_id | TEXT | Primary Key |
| session_id | TEXT | Foreign Key |
| rubric_version_id | TEXT | Foreign Key |
| transcript_version | INTEGER | Not Null |
| transcript_hash | TEXT | Optional |
| evaluator_model_run_id | TEXT | Foreign Key, Optional |
| overall_summary | TEXT | Optional |
| report_metadata | TEXT | JSON |
| status | TEXT | Not Null |
| created_at | TEXT | Not Null |

Possible statuses:

- pending
- completed
- failed
- requires_review

The evaluator must receive only the authorized evaluation input, not the restricted case database.

### 14.3 evaluation_items

Stores individual competency results.

| Field | Type | Constraints |
|---|---|---|
| evaluation_item_id | TEXT | Primary Key |
| evaluation_id | TEXT | Foreign Key |
| competency_id | TEXT | Not Null |
| rating_code | TEXT | Not Null |
| justification | TEXT | Optional |
| limitations | TEXT | Optional |

Allowed rating codes:

- 0
- 1
- 2
- 3
- NE

Constraint:

- A competency must not appear more than once within the same evaluation unless an explicitly versioned rubric permits multiple sub-items.

### 14.4 evaluation_evidence

Links evaluation results to supporting transcript messages.

| Field | Type | Constraints |
|---|---|---|
| evaluation_item_id | TEXT | Foreign Key |
| message_id | TEXT | Foreign Key |
| evidence_role | TEXT | Not Null |
| evidence_note | TEXT | Optional |

Composite Primary Key:

- evaluation_item_id
- message_id

Evaluation justifications must distinguish supporting evidence from missing evidence.

---

## 15. Audit Table

### 15.1 audit_events

Stores important system operations.

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
| metadata | TEXT | JSON |
| created_at | TEXT | Not Null |

Initial audit events include:

- session_created
- session_completed
- message_persisted
- event_accepted
- event_rejected
- state_transition_accepted
- state_transition_rejected
- evaluation_generated
- evaluation_failed
- memory_updated

Audit records must avoid unnecessary duplication of sensitive content.

---

## 16. Indexing Strategy

The initial implementation should include indexes for frequently accessed relationships.

Recommended indexes:

- case_versions.case_id
- simulation_runs.case_id
- simulation_runs.case_version_id
- sessions.run_id
- messages.session_id
- messages.session_id + sequence_number
- events.session_id
- events.event_type
- event_evidence.message_id
- state_snapshots.run_id
- state_transitions.run_id
- state_transitions.session_id
- memory_items.run_id
- evaluations.session_id
- evaluation_items.evaluation_id
- model_runs.session_id

Unique constraints and indexes must be selected based on actual query patterns and validated against the implemented schema.

---

## 17. Transaction and Consistency Rules

Operations involving multiple related records must use database transactions.

### 17.1 State Update Transaction

An accepted state transition should follow this sequence:

1. Validate the candidate transition.
2. Begin a database transaction.
3. Insert the transition record.
4. Create the resulting state snapshot.
5. Insert all state variable values.
6. Link the transition to the resulting snapshot.
7. Record the audit event.
8. Commit the transaction.

If any required operation fails, the transaction must be rolled back.

### 17.2 Session Completion

Session completion should:

1. Validate the session status.
2. Finalize the transcript version.
3. Persist any pending accepted events.
4. Record the completion timestamp.
5. Update the session status.
6. Record the audit event.

Evaluation generation should be a separate operation so that evaluation failure does not destroy a completed transcript.

### 17.3 Memory Updates

Memory updates must preserve:

- Previous versions.
- Source references.
- Information classification.
- Creation and update timestamps.

Contradictory information must not silently overwrite older records.

---

## 18. Database Access Boundaries

The application should expose separate repositories or services for different data categories.

| Component | Operational Database | Restricted Database |
|---|---|---|
| Therapist Interface | Authorized session data | No access |
| Patient Agent | Limited session context | Authorized context through Patient Context |
| Evaluator Agent | Authorized transcript, rubric, and evaluation data | No access |
| State Engine | Events and state records | No direct access by default |
| Memory Service | Authorized memory records | No direct access by default |
| Orchestrator | Session metadata and coordination | No unrestricted access by default |

The Evaluator Agent must receive an explicit EvaluationInput object.

It must never receive an unrestricted database session or repository that can query hidden case material.

---

## 19. Data Retention and Recovery

The initial system must support:

- Persistent session history.
- Historical case versions.
- Historical rubric versions.
- Historical state snapshots.
- Recovery after interrupted sessions.
- Database backup and restoration.
- Traceability of failed operations.

The system must not silently delete records required to reproduce a completed simulation.

Any deletion or modification of historical data must be an explicit, auditable operation.

The database must contain synthetic case information only during the initial MVP.

---

## 20. Initial Implementation Scope

The first database implementation will focus on:

1. Case and case-version storage.
2. Simulation runs and sessions.
3. Conversation messages.
4. Model execution metadata.
5. Structured interaction events.
6. State snapshots and transitions.
7. Longitudinal memory.
8. Rubric versions and evaluation reports.
9. Audit logging.
10. Restricted case data isolation.

Advanced analytics, distributed storage, multi-user access management, and cloud synchronization are outside the initial MVP scope.

---

## 21. Open Design Questions

The following decisions remain to be finalized:

- Should database migrations use a dedicated migration tool?
- Should the two SQLite databases be managed by separate repository interfaces?
- Should the restricted database be encrypted at rest?
- Should the application use a dedicated database service layer?
- How should concurrent session operations be handled?
- Should model input and output payloads be stored, hashed, or selectively retained?
- How should schema migrations preserve historical simulation reproducibility?
- Which records should be immutable at the database level?
- How should backups protect restricted case information?

These questions must be resolved before implementation.

---

**End of Document**