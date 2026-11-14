# TheraSim — Data Contracts

**Document Version:** 0.2
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14
**Architecture Reference:** MVP_DECISIONS.md

---

## 1. Purpose

This document defines the logical data contracts used by TheraSim.

It establishes the structures exchanged between the Orchestrator, Patient Agent, Evaluator Agent, Event Processing Service, Clinical State Engine, Memory Service, and persistence layer.

The contracts must ensure:

- Consistent data exchange.
- Explicit component responsibilities.
- Restricted case information isolation.
- Controlled disclosure tracking.
- Longitudinal simulation continuity.
- Evidence-linked state transitions.
- Session-level and longitudinal evaluation.
- Reproducibility.
- Structured validation and error handling.

These contracts are implementation specifications and will subsequently be represented using Pydantic models.

The MVP architecture decisions in `MVP_DECISIONS.md` take precedence over earlier provisional designs.

---

## 2. Core Data Objects

The initial implementation defines the following objects:

1. CaseDefinition
2. PublicCaseProfile
3. CaseFact
4. RestrictedCaseContext
5. CaseFactDisclosure
6. SimulationRun
7. SessionContext
8. PatientContext
9. TherapistMessage
10. PatientResponse
11. InteractionRequest
12. SessionTranscript
13. ClinicalState
14. StateTransitionProposal
15. StateSnapshot
16. SimulationEvent
17. LongitudinalMemory
18. EvaluationInput
19. EvaluationReport
20. ModelExecutionMetadata

Each object must have explicit ownership, validation requirements, and access restrictions.

---

## 3. Identifier and Timestamp Conventions

All primary identifiers must use UUID strings unless an explicitly defined identifier convention is required.

Examples:

- case_id
- case_version_id
- run_id
- session_id
- message_id
- event_id
- transition_id
- snapshot_id
- evaluation_id
- memory_id

All timestamps must:

- Use UTC.
- Follow ISO 8601.
- Include timezone information.
- Remain consistent across the application.

Example:

`2026-11-14T12:30:00Z`

All original transcript messages must be preserved without destructive modification.

---

## 4. CaseDefinition

CaseDefinition represents the complete logical definition of a synthetic client.

It is a conceptual aggregate, not an object that should be passed unrestricted to every component.

The case definition must be divided into explicitly authorized information objects.

### 4.1 Metadata

Required fields:

- case_id
- case_version_id
- case_code
- display_name
- modality
- supported_languages
- schema_version
- creation_timestamp

### 4.2 Information Separation

Case information is divided into:

1. PublicCaseProfile.
2. CaseFact registry.
3. RestrictedCaseContext.

These objects must be stored and retrieved according to their access boundaries.

The Evaluator Agent must never receive RestrictedCaseContext.

The Patient Agent must receive only the authorized PatientContext constructed by the Patient Context Service.

---

## 5. PublicCaseProfile

Represents the information that may be used to introduce a synthetic client to the trainee.

Fields:

- case_id
- case_version_id
- display_name
- age
- occupation
- presenting_concerns
- initial_disclosure
- language
- modality
- profile_version

The public profile must not contain hidden clinical formulation or undisclosed personal history.

Therapist-visible information must still follow the disclosure rules configured for the scenario.

Availability in the public case registry does not automatically imply permission to display every field to the therapist.

---

## 6. CaseFact

Represents an individually identifiable information item within a synthetic case.

Every relevant case fact must have a stable identifier within its case version.

Example identifiers:

- AVA-FACT-001
- AVA-FACT-002
- AVA-FACT-003

Fields:

- case_fact_id
- case_id
- case_version_id
- fact_category
- information_class
- content
- disclosure_policy
- relevance_metadata
- created_at

### 6.1 Information Classes

Allowed classifications:

- established_fact
- case_hypothesis
- unspecified_information

These classifications distinguish established fictional history from hypotheses and information that has not been defined.

The Patient Agent must not present a case hypothesis as an established personal fact.

### 6.2 Disclosure Policies

Initial policy categories:

- initial_disclosure
- contextually_disclosable
- restricted
- not_applicable

These categories are internal simulation metadata.

They must not be directly exposed through the Therapist Interface.

Disclosure must remain context-sensitive and must not follow an automatic fixed sequence.

---

## 7. RestrictedCaseContext

Contains restricted information required for the simulation.

Fields may include:

- case_id
- case_version_id
- clinical_formulation
- relevant_personal_history
- maintaining_factors
- avoidance_patterns
- hypothesized_functions
- restricted_case_facts
- initial_safety_baseline
- patient_simulation_instructions

This information is available only through the authorized Patient Context Service.

The complete restricted context must not be transferred to:

- Therapist Interface.
- Evaluator Agent.
- Public API responses.
- General application logs.
- Unrelated internal services.

The State Engine must not receive unrestricted access to this object.

---

## 8. CaseFactDisclosure

Represents the disclosure status of a specific case information item during a simulation run.

Disclosure records are run-specific because the same synthetic case may be used in different simulation runs with different interaction histories.

Fields:

- disclosure_id
- run_id
- case_id
- case_version_id
- case_fact_id
- disclosure_status
- source_message_id
- evidence_start_offset
- evidence_end_offset
- validation_method
- validation_notes
- created_at
- updated_at

### 8.1 Disclosure Statuses

Allowed values:

- not_disclosed
- candidate_disclosed
- confirmed_disclosed
- requires_review

### 8.2 Disclosure Rules

1. The Patient Agent may propose a disclosure annotation.
2. The annotation must reference an existing case_fact_id.
3. The source message must exist.
4. The evidence must be associated with the patient response.
5. The backend must validate the proposal.
6. Ambiguous disclosure must remain a candidate or require review.
7. Only validated disclosure may be recorded as confirmed_disclosed.
8. A confirmed disclosure must retain its source message reference.

A model-generated annotation alone is not sufficient to establish a confirmed disclosure.

The system must preserve disclosure history rather than silently replace previous records.

---

## 9. SimulationRun

Represents one longitudinal execution of a synthetic case.

Fields:

- run_id
- case_id
- case_version_id
- modality
- language
- status
- configuration_version
- started_at
- completed_at
- created_at

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

### 9.1 MVP Session Structure

The initial MVP contains exactly three sequential sessions per simulation run.

A run must reference one specific case version.

Historical records must not be silently transferred to a different case version.

---

## 10. SessionContext

Represents the context of an individual simulation session.

Fields:

- session_id
- run_id
- case_id
- case_version_id
- session_number
- modality
- language
- status
- transcript_version
- started_at
- ended_at
- created_at

Possible statuses:

- initialized
- active
- completed
- interrupted
- failed

### 10.1 Session Ordering

The initial MVP requires:

- Session 1 before Session 2.
- Session 2 before Session 3.
- No simultaneous active interaction generation within the same session.

A later session must use the validated historical context from previous completed sessions.

An incomplete or failed session must not be treated automatically as successfully completed.

---

## 11. PatientContext

PatientContext is the explicit input object constructed by the Patient Context Service.

It contains the minimum information required for the Patient Agent to simulate the client.

### 11.1 Required Fields

- case_id
- case_version_id
- run_id
- session_id
- session_number
- language
- modality
- public_identity
- relevant_restricted_context
- relevant_case_facts
- current_clinical_state
- disclosure_statuses
- relevant_longitudinal_memory
- recent_transcript
- therapist_message
- prompt_version

### 11.2 Access Requirements

The Patient Agent may receive relevant restricted information.

However:

- It must not receive database credentials.
- It must not receive unrestricted repository access.
- It must not receive unrelated synthetic cases.
- It must not receive application secrets.
- It must not modify disclosure records directly.
- It must not modify canonical clinical state.

PatientContext must be constructed through explicit application logic.

The complete CaseDefinition must not be inserted automatically.

---

## 12. TherapistMessage

Represents a message submitted by the trainee.

Fields:

- message_id
- run_id
- session_id
- sequence_number
- role
- content
- timestamp

Allowed role:

- therapist

The original therapist message must be preserved exactly as submitted.

Message sequence numbers must be unique within the session.

Therapist messages are untrusted conversational content and must not be interpreted as system instructions by language-model agents.

---

## 13. PatientResponse

Represents a response generated by the Patient Agent.

Fields:

- message_id
- run_id
- session_id
- sequence_number
- role
- content
- response_status
- model_run_id
- prompt_version
- created_at

Allowed role:

- patient

The response must pass schema validation before becoming therapist-visible.

### 13.1 Optional Interaction Annotations

The Patient Agent may provide candidate annotations.

Each annotation may contain:

- candidate_event_type
- related_case_fact_id
- evidence_description
- evidence_span
- uncertainty_notes

These annotations are proposals only.

They must not automatically establish disclosure, memory, psychological events, or state transitions.

Internal reasoning and hidden prompts must never be included in the therapist-visible response.

---

## 14. InteractionRequest

Represents one therapist message submission operation.

This object provides request tracking and idempotency.

Fields:

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

Possible processing statuses:

- in_progress
- completed
- failed

### 14.1 Idempotency Rules

The combination of session_id and idempotency_key must be unique.

When the same key is reused with an identical request payload:

- The system must not create duplicate therapist messages.
- The system must not generate duplicate patient responses.
- The existing operation result or status must be returned.

When the same key is reused with a different request payload:

- The operation must be rejected with an idempotency conflict.

Failed operations must retain their original request record.

Retry behavior must be controlled and must not create duplicate interaction records.

---

## 15. SessionTranscript

Represents the complete chronological interaction of one session.

Fields:

- transcript_id
- run_id
- session_id
- case_version_id
- transcript_version
- messages
- content_hash
- created_at
- finalized_at

Each message must preserve:

- message_id
- role
- content
- sequence_number
- timestamp

The transcript must remain immutable after session completion.

Corrections must be represented through explicit versioned operations.

The evaluation process must reference the exact transcript version used.

---

## 16. ClinicalState

Represents the structured simulation state of the synthetic client.

Initial variables:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Each variable uses an integer range from 0 to 4.

These values are engineering parameters for simulation purposes.

They are not validated psychological measurements or clinical scores.

### 16.1 Initial AVA-001 Values

| Variable | Initial Value |
|---|---:|
| therapeutic_alliance | 2 |
| disclosure_readiness | 1 |
| experiential_avoidance | 4 |
| willingness | 1 |
| values_clarity | 2 |
| committed_action_readiness | 1 |

### 16.2 State Management Rules

1. The initial state must be persisted before the first interaction.
2. Previous state snapshots must remain accessible.
3. The Patient Agent may receive the authorized current state.
4. The Evaluator Agent must not receive hidden state variables.
5. The Patient Agent must not modify canonical state.
6. The Event Processing Service must not modify canonical state.
7. The State Engine is the only component authorized to accept canonical state transitions.

Until each variable has operational behavioral anchors and reviewed transition rules, psychological state values must not be automatically changed through unrestricted LLM interpretation.

When evidence is insufficient, the current value must remain unchanged or the proposal must require review.

---

## 17. StateTransitionProposal

Represents a proposed change to a specific clinical simulation variable.

Fields:

- transition_id
- run_id
- session_id
- variable_name
- previous_value
- proposed_value
- evidence_message_ids
- evidence_description
- transition_rule_id
- transition_rule_version
- confidence
- validation_status
- uncertainty_notes
- created_at
- validated_at

Possible validation statuses:

- pending
- accepted
- rejected
- requires_review

### 17.1 Transition Rules

1. A therapist intervention alone cannot justify a state change.
2. Every proposed transition must reference valid evidence.
3. Variable names must belong to the approved schema.
4. Values must remain within the 0–4 range.
5. Duplicate evidence must not produce repeated state changes.
6. Accepted changes must use an applicable versioned transition rule.
7. Rejected and uncertain proposals must remain available for audit.
8. No language model may directly overwrite canonical state.

The confidence field represents system-level uncertainty and must not be interpreted as clinical certainty.

---

## 18. StateSnapshot

Represents an immutable snapshot of the simulation state.

Fields:

- snapshot_id
- run_id
- session_id
- previous_snapshot_id
- state_schema_version
- snapshot_reason
- variable_values
- accepted_transition_ids
- created_at

A new snapshot may be created after an accepted transition or an explicitly defined checkpoint.

Every accepted state change must be recoverable through historical records.

Restoring an earlier state must create an auditable operation rather than silently deleting later history.

---

## 19. SimulationEvent

Represents an event within the simulation.

The MVP distinguishes between deterministic operational events and candidate behavioral events.

### 19.1 Deterministic Events

Examples:

- simulation_run_created
- session_started
- therapist_message_received
- patient_response_generated
- session_completed
- evaluation_generated
- model_execution_failed

These events are created by application operations.

### 19.2 Candidate Behavioral Events

Examples:

- emotional_experience_disclosed
- willingness_expressed
- experiential_avoidance_observed
- cognitive_defusion_response_observed
- values_clarification_observed
- homework_agreed
- intervention_declined

These events may require model assistance or review.

They are not automatically accepted as established psychological observations.

### 19.3 Event Fields

- event_id
- run_id
- session_id
- event_type
- actor
- source_message_ids
- evidence_span
- event_payload
- extraction_method
- extractor_version
- event_status
- idempotency_key
- created_at
- validated_at

Possible extraction methods:

- application_rule
- model_assisted
- manual

Possible event statuses:

- candidate
- accepted
- rejected
- requires_review

The initial MVP prioritizes deterministic application events.

Model-assisted behavioral extraction is optional and may be introduced behind the same internal service interface.

The Event Processing Service is not an independent mandatory LLM agent.

---

## 20. LongitudinalMemory

Represents selected information retained between sessions.

Fields:

- memory_id
- run_id
- source_session_id
- memory_type
- information_class
- content
- source_message_ids
- confidence
- status
- memory_version
- created_at
- updated_at

### 20.1 Initial Memory Categories

- disclosed_facts
- relevant_client_experiences
- therapist_interventions
- agreed_homework
- reported_homework_outcomes
- unresolved_topics
- relevant_interaction_patterns
- accepted_state_transitions

### 20.2 Information Classes

Each memory item must have an explicit classification:

- confirmed_fact
- explicit_disclosure
- therapist_hypothesis
- system_generated_summary
- reported_outcome
- structured_observation

These classifications must remain distinct.

A therapist hypothesis must never be silently converted into a confirmed client fact.

### 20.3 Memory Rules

1. Every memory item must preserve its source references.
2. Memory must not replace the original transcript.
3. Contradictory information must remain traceable.
4. Updated memory must preserve historical versions.
5. Irrelevant information must not be included automatically in PatientContext.
6. Memory generation must not directly modify canonical clinical state.

The initial implementation prioritizes structured memory records and deterministic selection.

---

## 21. EvaluationInput

Represents the authorized input provided to the Evaluator Agent.

Two evaluation scopes are supported.

### 21.1 Session-Level Evaluation

Required fields:

- evaluation_id
- evaluation_scope
- run_id
- session_id
- transcript_id
- transcript_version
- transcript_hash
- modality
- language
- rubric_id
- rubric_version
- rubric_definition
- therapist_visible_context
- evaluation_instructions

The evaluator receives the finalized transcript of one completed session.

### 21.2 Longitudinal Evaluation

Required fields:

- evaluation_id
- evaluation_scope
- run_id
- case_version_id
- modality
- language
- rubric_id
- rubric_version
- session_transcripts
- therapist_visible_context_by_session
- evaluation_instructions

The longitudinal evaluator receives the three finalized session transcripts belonging to the same simulation run.

Each transcript entry must contain:

- session_id
- session_number
- transcript_id
- transcript_version
- transcript_hash
- chronological_messages

The order of sessions must be preserved.

### 21.3 Evaluation Scope Values

Allowed values:

- session
- longitudinal

### 21.4 Evaluator Access Restrictions

The Evaluator Agent may access:

- Finalized therapist and patient messages.
- Applicable versioned rubric.
- Therapist-visible context.
- Authorized session metadata.
- Evidence identifiers and transcript versions.

It must not access:

- RestrictedCaseContext.
- Hidden case formulation.
- Undisclosed personal history.
- Internal Patient Agent instructions.
- Future planned responses.
- Hidden disclosure policies.
- Private state variables unavailable to the therapist.
- Unvalidated candidate events.
- Unrestricted database connections.

The EvaluatorInput must be constructed using an explicit allowlist.

---

## 22. EvaluationReport

Represents the structured output generated by the Evaluator Agent.

### 22.1 Common Fields

- evaluation_id
- evaluation_scope
- run_id
- session_id
- rubric_id
- rubric_version
- report_status
- overall_summary
- strengths
- improvement_areas
- competency_results
- missing_evidence
- safety_observations
- uncertainty_notes
- evaluator_model
- evaluator_prompt_version
- generated_at

For session-level reports, session_id is required.

For longitudinal reports, session_id is null and run_id is required.

### 22.2 CompetencyResult

Each competency result must contain:

- competency_id
- rating
- justification
- evidence_references
- alternative_response
- limitations
- uncertainty_notes

Each evidence reference may contain:

- message_id
- evidence_start_offset
- evidence_end_offset
- evidence_excerpt
- evidence_role

The original message identifier must always be preserved.

### 22.3 Rating Rules

Ratings must follow the applicable rubric.

For the initial ACT rubric:

- 0
- 1
- 2
- 3
- NE

NE means Not Enough Evidence.

NE must not be converted automatically to zero.

No aggregate numerical score will be produced unless a future explicitly versioned rubric defines and justifies an aggregation method.

### 22.4 Evaluation Restrictions

The report must distinguish:

- Observed therapist behavior.
- Interpretation of the interaction.
- Missing evidence.
- Uncertainty.

The system must not present these reports as validated measures of therapist competence or professional certification.

---

## 23. ModelExecutionMetadata

Represents metadata about a language-model execution.

Fields:

- model_run_id
- run_id
- session_id
- component
- provider
- model_identifier
- model_version
- model_artifact_digest
- prompt_id
- prompt_version
- input_schema_version
- output_schema_version
- generation_parameters
- input_hash
- output_hash
- random_seed
- execution_status
- output_validation_status
- started_at
- completed_at

Possible components:

- patient_agent
- evaluator_agent
- optional_event_extractor
- optional_memory_processor

The initial MVP requires two primary LLM agents.

Event extraction and memory processing do not require separate simultaneously running models.

The metadata must record model information available from the local runtime.

The system must not claim exact reproducibility when the model runtime cannot guarantee deterministic execution.

---

## 24. Component Communication Contracts

### 24.1 Orchestrator

Input:

- Authorized API requests.
- Run and session metadata.
- Validated component outputs.

Output:

- Coordinated simulation operations.
- Session lifecycle events.
- Persisted records.
- Authorized API responses.

The Orchestrator must not invent psychological state changes.

### 24.2 Patient Context Service

Method:

`build_patient_context(run_id, session_id)`

Input:

- run_id
- session_id

Output:

- PatientContext

Responsibilities:

- Retrieve the correct case version.
- Retrieve relevant restricted case context.
- Retrieve case fact definitions.
- Retrieve disclosure statuses.
- Retrieve current state.
- Retrieve relevant longitudinal memory.
- Apply disclosure policies.
- Exclude unrelated information.

It is the authorized access path to restricted case information.

### 24.3 Patient Agent

Method:

`generate_response(patient_context, therapist_message)`

Input:

- Authorized PatientContext.
- Latest TherapistMessage.

Output:

- PatientResponse.
- Optional candidate interaction annotations.

It must not directly modify persistent state or disclosure records.

### 24.4 Event Processing Service

Method:

`process_interaction(transcript_segment, application_events)`

Input:

- Validated transcript messages.
- Application-generated operational events.
- Optional approved behavioral event proposals.

Output:

- Accepted deterministic events.
- Candidate behavioral events.
- Evidence references.
- Processing metadata.

The initial implementation should prioritize deterministic events.

Optional model-assisted extraction may be introduced later.

### 24.5 Clinical State Engine

Method:

`validate_transition(current_state, proposal, evidence)`

Input:

- Current state snapshot.
- StateTransitionProposal.
- Validated evidence references.
- Applicable transition rule.

Output:

- Accepted, rejected, or review-required decision.
- New StateSnapshot when a transition is accepted.

The engine must enforce deterministic validation rules.

### 24.6 Memory Service

Initial operations:

- `retrieve_memory(run_id, session_id)`
- `create_memory_candidates(transcript, accepted_events)`
- `validate_memory_updates(candidates)`
- `persist_memory_updates(accepted_items)`

The service must preserve source references and information classifications.

### 24.7 Evaluator Agent

Method:

`evaluate(evaluation_input)`

Input:

- Session-level or longitudinal EvaluationInput.
- Explicit rubric version.
- Authorized transcript information.

Output:

- Structured EvaluationReport.

The same Evaluator Agent may handle both evaluation scopes, provided the input schema explicitly identifies the scope.

---

## 25. Data Access Matrix

| Data Category | Patient Agent | Evaluator Agent | State Engine | Therapist |
|---|---|---|---|---|
| Public case profile | Yes | No | No | Authorized subset |
| Restricted case context | Limited, authorized | No | No | No |
| Case facts | Relevant subset | No | No | Disclosed facts only |
| Disclosure status | Relevant subset | No | No | No |
| Current clinical state | Yes | No | Yes | No |
| Therapist messages | Relevant context | Yes | Evidence only | Yes |
| Patient responses | Relevant context | Yes | Evidence only | Yes |
| Longitudinal memory | Relevant subset | No | No | No |
| Evaluation rubric | No | Yes | No | No |
| Evaluation report | No | Generates | No | Yes |

The Orchestrator coordinates access but must not bypass the explicit service interfaces.

Technical access restrictions must be enforced by the application, not merely described in this table.

---

## 26. Data Integrity and Reproducibility

The following rules apply to all data objects:

1. Every record must have a unique identifier.
2. Every session must reference one specific case version.
3. Every evaluation must reference one specific rubric version.
4. Session-level evaluations must reference one finalized transcript version.
5. Longitudinal evaluations must reference all three finalized session transcript versions.
6. Model and prompt versions must be recorded.
7. State changes must be auditable.
8. Disclosure changes must reference supporting messages.
9. Missing and uncertain information must be represented explicitly.
10. Failed operations must be recorded.
11. Historical records must remain available.
12. Data contracts must be independently versioned.
13. Original transcript messages must remain unchanged after session completion.
14. Repeated requests must not produce duplicate accepted interactions.

---

## 27. Validation Requirements

Every object must be validated before it is accepted into persistent storage or transferred to another component.

Validation must include:

- Required fields.
- Field types.
- Identifier formats.
- Allowed enumerated values.
- Valid ranges.
- Referential integrity.
- Session and run consistency.
- Case version consistency.
- Schema version compatibility.
- Information access authorization.

Model-generated outputs must always be treated as untrusted until validated.

---

## 28. Versioning and Migration

The current document version is 0.2.

The implementation must independently version:

- Data schemas.
- Case definitions.
- Case facts.
- Session transcript formats.
- State schemas.
- Event schemas.
- Memory structures.
- Evaluation reports.
- Model input and output contracts.

A schema update must not silently reinterpret historical data.

Migrations must preserve historical case, rubric, transcript, and model references.

---

## 29. Initial MVP Implementation Scope

The first implementation will support:

1. One synthetic ACT case.
2. One simulation run with three sequential sessions.
3. Two primary LLM agents.
4. A PatientContext service.
5. An internal Event Processing Service.
6. A deterministic Clinical State Engine.
7. Structured disclosure tracking.
8. Structured longitudinal memory.
9. Session-level evaluation.
10. Run-level longitudinal evaluation.
11. Evidence-linked reports.
12. Versioned model and prompt metadata.
13. Local execution through Ollama.

---

## 30. Open Design Questions

The following issues remain subject to implementation testing:

- Which case fact items require explicit disclosure tracking?
- Which disclosure candidates can be validated deterministically?
- Which state variables can receive reliable operational behavioral anchors?
- How much transcript history should be included in PatientContext?
- How should memory relevance be determined?
- How should evaluation uncertainty be represented consistently?
- Which event categories should remain manual or rule-based?
- How should transcript hashes be generated?
- How should the application recover incomplete interaction requests?
- How should model-specific structured output differences be handled?

These questions must be resolved through implementation and testing.

---

**End of Document**