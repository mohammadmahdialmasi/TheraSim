# TheraSim — Data Contracts

**Document Version:** 0.1  
**Project Status:** Research Prototype / Pre-MVP  
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the data structures and communication contracts between the core components of TheraSim.

The purpose is to ensure:

- Consistent data exchange.
- Separation of component responsibilities.
- Protection of hidden synthetic case information.
- Reproducibility of simulation sessions.
- Traceability of clinical state transitions.
- Structured and evidence-grounded evaluation.

These contracts are technology-independent specifications. They will later be implemented using Pydantic models.

---

## 2. Core Data Objects

The initial system defines the following primary data objects:

1. CaseDefinition
2. SessionContext
3. TherapistMessage
4. PatientResponse
5. ClinicalState
6. StateTransitionEvent
7. SessionTranscript
8. EvaluationRequest
9. EvaluationReport
10. LongitudinalMemory

Each object must have a clearly defined purpose and access boundary.

---

## 3. CaseDefinition

Represents the complete synthetic client definition.

It contains both information available to the Patient Agent and information that must remain hidden during the simulation.

### 3.1 Public Case Information

- case_id
- display_name
- age
- occupation
- presenting_concerns
- initial_disclosure

### 3.2 Restricted Case Information

- clinical_formulation
- relevant_personal_history
- maintaining_factors
- avoidance_patterns
- hypothesized_functions
- undisclosed_information
- initial_safety_baseline

### 3.3 Metadata

- case_version
- therapeutic_modality
- language
- creation_date

**Access Rule:** The complete CaseDefinition is restricted to authorized internal components. The Patient Agent receives only the information required to simulate the client. The Evaluator Agent must not receive restricted information.

---

## 4. SessionContext

Represents the context of an individual simulation session.

Fields:

- session_id
- case_id
- session_number
- modality
- language
- start_timestamp
- end_timestamp
- session_status
- model_configuration
- case_version

Possible session statuses:

- initialized
- active
- completed
- interrupted
- failed

---

## 5. TherapistMessage

Represents a message submitted by the trainee.

Fields:

- message_id
- session_id
- sequence_number
- role
- content
- timestamp

The role must be:

- therapist

The original message must be preserved without modification.

---

## 6. PatientResponse

Represents the synthetic client's response.

Fields:

- message_id
- session_id
- sequence_number
- role
- content
- timestamp
- generation_metadata

The role must be:

- patient

Generation metadata may include:

- model_identifier
- model_version
- prompt_version
- generation_parameters

Internal reasoning and hidden prompts must never be included in the therapist-visible response.

---

## 7. ClinicalState

Represents the structured simulation state of the synthetic client at a specific point in time.

Initial variables:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

Each initial variable uses an integer range from 0 to 4.

These values are engineering parameters for simulation purposes. They are not validated psychological scales or clinical measurements.

Additional fields:

- state_id
- case_id
- session_id
- state_version
- updated_at

The system must preserve previous state snapshots rather than overwrite historical states.

---

## 8. StateTransitionEvent

Represents a proposed or accepted change in the structured clinical simulation state.

Fields:

- event_id
- session_id
- case_id
- variable_name
- previous_value
- proposed_value
- accepted_value
- triggering_message_ids
- evidence_summary
- transition_rule_id
- confidence
- validation_status
- timestamp

Possible validation statuses:

- proposed
- accepted
- rejected
- requires_review

Rules:

1. Every accepted transition must have an identifiable reason.
2. Every transition must reference relevant conversational evidence or an explicitly defined simulation rule.
3. Invalid numerical values must be rejected.
4. State transitions must be recorded as events.
5. Historical state values must remain recoverable.
6. The LLM must not directly overwrite the ClinicalState.

The confidence field represents system-level uncertainty about a proposed transition. It must not be interpreted as clinical certainty.

---

## 9. SessionTranscript

Represents the complete chronological interaction within a session.

Fields:

- transcript_id
- session_id
- case_id
- session_number
- messages
- created_at
- transcript_version

Each message must preserve:

- message_id
- role
- content
- sequence_number
- timestamp

The transcript must be immutable after session completion. Corrections must be represented through a separate version or audit event.

---

## 10. EvaluationRequest

Represents the information submitted to the Evaluator Agent.

Fields:

- evaluation_id
- session_id
- transcript_id
- rubric_id
- rubric_version
- modality
- language
- authorized_session_context

The Evaluator Agent may access:

- Complete session transcript.
- Applicable evaluation rubric.
- Therapist-visible session context.
- Relevant evaluation instructions.

The Evaluator Agent must not access:

- Hidden clinical formulation.
- Undisclosed personal history.
- Internal Patient Agent prompts.
- Future planned responses.
- Private state variables unavailable to the therapist.

This separation is mandatory to reduce evaluation bias.

---

## 11. EvaluationReport

Represents the structured evaluation generated after session completion.

Fields:

- report_id
- session_id
- evaluation_id
- rubric_id
- rubric_version
- overall_summary
- competency_results
- strengths
- improvement_areas
- evidence_references
- missing_evidence
- safety_observations
- uncertainty_notes
- generated_at
- evaluator_model
- evaluator_prompt_version

Each competency result must include:

- competency_id
- rating
- justification
- supporting_message_ids
- limitations

Ratings must follow the rubric's defined scale, including NE where appropriate.

The system must not present the evaluation as a validated measure of therapist competence.

---

## 12. LongitudinalMemory

Represents information preserved between simulation sessions.

Fields:

- memory_id
- case_id
- session_id
- memory_type
- content
- source_message_ids
- confidence
- created_at
- memory_version

Initial memory categories:

- disclosed_personal_information
- recurring_patterns
- therapeutic_interaction_history
- agreed_homework
- reported_homework_outcomes
- unresolved_topics
- state_transition_history

Memory must distinguish between:

1. Information explicitly disclosed by the synthetic client.
2. Therapist interpretations or hypotheses.
3. System-generated summaries.
4. Structured state changes.

These categories must never be treated as interchangeable.

---

## 13. Component Communication Contracts

### Patient Agent

**Input:**

- Authorized case information.
- Current ClinicalState.
- Relevant LongitudinalMemory.
- Current SessionContext.
- Latest TherapistMessage.

**Output:**

- PatientResponse.
- Optional structured interaction annotations for internal processing.

### Clinical State Engine

**Input:**

- Current ClinicalState.
- Candidate StateTransitionEvent.
- Relevant transcript evidence.
- Transition rules.

**Output:**

- Accepted or rejected StateTransitionEvent.
- Updated ClinicalState snapshot.

### Evaluator Agent

**Input:**

- EvaluationRequest.
- SessionTranscript.
- Authorized session context.
- Versioned rubric.

**Output:**

- Structured EvaluationReport.

### Orchestrator

**Input:**

- User commands.
- Session metadata.
- Component outputs.

**Output:**

- Coordinated execution.
- Session lifecycle events.
- Persisted records.

---

## 14. Data Integrity and Reproducibility

The following rules apply to all core data objects:

1. Every record must have a unique identifier.
2. Every session must reference a specific case version.
3. Every evaluation must reference a specific rubric version.
4. Model and prompt versions must be recorded.
5. Timestamps must use a consistent timezone standard, preferably UTC.
6. Historical session data must remain available.
7. State changes must be auditable.
8. Missing or uncertain information must be represented explicitly rather than fabricated.
9. Failed or incomplete operations must be recorded.
10. Data contracts must be versioned.

---

## 15. Initial Privacy and Access Rules

The system must implement explicit access boundaries.

| Data Category | Patient Agent | Evaluator Agent | Therapist |
|---|---|---|---|
| Public case information | Yes | No | Yes, when disclosed |
| Hidden case formulation | Limited | No | No |
| Current simulation state | Yes | No | No |
| Session transcript | Current context | Yes | Yes |
| Evaluation rubric | No | Yes | No |
| Evaluation report | No | Generates | Yes |
| Longitudinal memory | Relevant subset | No | No |

The table defines logical access boundaries. Technical enforcement will be implemented separately.

---

## 16. Open Design Questions

The following issues require further investigation:

- How should the system extract structured events from natural-language conversations?
- How should contradictory information be represented?
- How should memory be updated when new disclosures contradict earlier information?
- How should uncertainty be calibrated?
- How should evaluation evidence be linked to exact transcript segments?
- How should state transitions be validated?
- How should data access be enforced at the API and database levels?
- How should multilingual data be normalized without losing meaning?

---

**End of Document**