# TheraSim — State Transitions and Event System

**Document Version:** 0.1
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the event-driven mechanism responsible for tracking and validating changes in the structured state of a synthetic client across psychotherapy simulation sessions.

The system must ensure that:

- State changes are supported by observable conversational evidence.
- Therapeutic interventions do not automatically produce positive state changes.
- The synthetic client's responses remain consistent with the case formulation.
- Changes are traceable and reversible through historical snapshots.
- Uncertain interpretations are not treated as established facts.
- State updates remain reproducible and auditable.

The State Transition System is an engineering mechanism for controlling a simulation. It is not a validated clinical assessment instrument.

---

## 2. Architectural Overview

The proposed system consists of five logical components:

1. Event Collector
2. Event Annotation / Extraction Layer
3. Transition Rule Engine
4. State Validator
5. State History Manager

These are logical responsibilities and do not necessarily require five independent services.

### Processing Flow

1. A therapist submits a message.
2. The Patient Agent generates a response.
3. The conversation is appended to the session transcript.
4. Relevant interaction events are identified.
5. Candidate state transitions may be proposed.
6. The Transition Rule Engine checks applicable rules.
7. The State Validator accepts, rejects, or flags the proposal.
8. An accepted transition creates a new state snapshot.
9. The event and its supporting evidence are persisted.

The original conversation must remain unchanged throughout this process.

---

## 3. Event System

An event represents an observable interaction or a relevant occurrence within the simulation.

Events provide the traceable basis for state updates and longitudinal memory.

### 3.1 Initial Event Categories

#### A. Interaction Events

- therapist_message_received
- patient_response_generated
- session_started
- session_completed
- session_interrupted

#### B. Disclosure Events

- personal_information_disclosed
- emotional_experience_disclosed
- relevant_history_disclosed
- sensitive_topic_approached
- disclosure_withdrawn_or_corrected

#### C. Psychological Process Events

- experiential_avoidance_observed
- willingness_expressed
- cognitive_fusion_observed
- defusion_response_observed
- present_moment_awareness_observed
- values_clarification_observed
- value_consistent_action_reported

#### D. Therapeutic Interaction Events

- therapist_intervention_attempted
- intervention_explained
- intervention_accepted
- intervention_declined
- intervention_modified
- misunderstanding_detected
- therapeutic_repair_observed

#### E. Longitudinal Events

- homework_agreed
- homework_declined
- homework_attempted
- homework_completed
- homework_not_completed
- homework_outcome_reported

#### F. Safety Events

- safety_concern_detected
- direct_risk_question_asked
- safety_information_disclosed
- predefined_safety_protocol_triggered

Safety events must be processed through explicit safety rules. They must not be reduced to ordinary psychological state scores.

---

## 4. Event Data Structure

Each event must contain the following fields:

| Field | Description |
|---|---|
| event_id | Unique identifier |
| session_id | Related session |
| case_id | Related synthetic case |
| event_type | Event category |
| actor | Source of the event |
| sequence_number | Position in the interaction |
| source_message_ids | Supporting transcript messages |
| evidence_span | Exact text or character offsets, when available |
| event_payload | Structured event-specific data |
| extraction_method | Rule-based, model-assisted, or manual |
| extractor_version | Extraction logic version |
| event_status | Candidate, accepted, rejected, or requires review |
| timestamp | Event creation time |

An event must distinguish between:

- Directly observed conversational content.
- A structured interpretation of that content.
- A system-generated hypothesis.

These categories must not be conflated.

---

## 5. State Variables and Operational Boundaries

The initial ACT simulation uses the following state variables:

| Variable | Meaning within the simulation |
|---|---|
| therapeutic_alliance | Simulated quality of the therapeutic interaction |
| disclosure_readiness | Simulated readiness to share relevant information |
| experiential_avoidance | Simulated tendency to avoid difficult private experiences or situations |
| willingness | Simulated openness to experiencing difficult internal experiences |
| values_clarity | Simulated clarity regarding personally meaningful directions |
| committed_action_readiness | Simulated readiness to undertake value-consistent behavior |

Each variable uses an integer range from 0 to 4.

### Important Restrictions

1. These values are engineering parameters, not validated psychological measurements.
2. The values must not be presented as standardized clinical scores.
3. Each variable requires its own operational definition and level-specific behavioral anchors before implementation.
4. Variables must not be assumed to represent independent psychological constructs.
5. A change in one variable must not automatically change another variable.
6. The system must permit improvement, deterioration, stability, and uncertainty.

The same numerical value may represent different observable patterns across different variables. Therefore, a universal interpretation of the 0–4 scale is insufficient.

---

## 6. Transition Rules

A state transition represents a proposed change in one or more structured simulation variables.

### 6.1 General Rules

1. A therapist intervention alone cannot justify a state change.
2. A positive patient response does not automatically justify improvement.
3. A single intervention must not automatically increase willingness, alliance, or values clarity.
4. Every accepted transition must reference supporting evidence.
5. A state variable must remain unchanged when available evidence is insufficient.
6. State transitions may be positive, negative, or neutral.
7. Transitions must remain within the defined numerical range.
8. Contradictory evidence must be retained rather than silently discarded.
9. Repeated processing of the same evidence must not create duplicate transitions.
10. Large or poorly supported changes must be flagged for review.

### 6.2 Evidence Requirements

A candidate transition must include:

- Target variable.
- Previous value.
- Proposed value.
- Evidence message identifiers.
- Evidence description.
- Applicable transition rule.
- Uncertainty information.

Evidence should preferentially represent the synthetic client's response or reported behavior.

The occurrence of a therapist technique is not sufficient evidence of a psychological change.

### 6.3 Example

**Scenario:**

The therapist introduces a cognitive defusion exercise.

**Incorrect behavior:**

The system automatically increases willingness from 1 to 2 because the therapist used an ACT technique.

**Expected behavior:**

The system waits for the synthetic client's response.

Possible outcomes:

- The client engages with the exercise and describes a changed relationship with the thought.
- The client participates but reports no meaningful change.
- The client declines the exercise.
- The client becomes uncomfortable or more avoidant.
- The available response is ambiguous.

Only an outcome supported by the defined transition rules can justify a state update.

Participation must not be equated with therapeutic effectiveness.

---

## 7. Transition Validation

The State Validator checks each proposed transition before it can modify the current state.

### 7.1 Validation Checks

- Is the target variable valid?
- Is the proposed value within the permitted range?
- Does the source evidence exist?
- Do the referenced message identifiers belong to the correct session?
- Does the evidence actually support the proposed direction of change?
- Is an applicable transition rule defined?
- Has this evidence already been processed?
- Does the transition contradict stronger available evidence?
- Does the proposal require human review?

### 7.2 Validation Outcomes

| Outcome | Meaning |
|---|---|
| accepted | All mandatory checks passed |
| rejected | One or more mandatory checks failed |
| requires_review | Evidence or interpretation is ambiguous |
| pending | Validation has not been completed |

A rejected or uncertain proposal must not modify the current state.

---

## 8. Role of Language Models

Language models may assist with identifying relevant conversational evidence and proposing candidate events.

They must not directly modify the canonical ClinicalState.

### Permitted Model Responsibilities

- Identify potentially relevant statements.
- Classify candidate interaction events.
- Suggest relevant state variables.
- Extract evidence references.
- Describe uncertainty.
- Propose possible state transitions for validation.

### Restricted Model Responsibilities

- Directly overwrite stored state variables.
- Invent evidence that is absent from the transcript.
- Treat therapist intention as evidence of client change.
- Convert an uncertain interpretation into a confirmed fact.
- Generate arbitrary numerical improvements.
- Bypass the State Validator.

The deterministic validation layer remains responsible for accepting or rejecting proposed changes.

---

## 9. State Transition Event Structure

An accepted or rejected transition must produce a structured record.

Required fields:

- transition_id
- case_id
- session_id
- event_id
- variable_name
- previous_value
- proposed_value
- accepted_value
- transition_direction
- evidence_message_ids
- transition_rule_id
- validation_status
- uncertainty_notes
- timestamp

The proposed value and accepted value must remain separate.

For example, a model may propose a transition from 1 to 3, but the validation layer may reject it or require additional review.

The system must preserve both the proposal and its validation result.

---

## 10. State Snapshot Management

The system must store state snapshots rather than destructively replacing historical state.

Each snapshot must contain:

- state_snapshot_id
- case_id
- session_id
- previous_snapshot_id
- state_version
- variable_values
- associated_transition_ids
- created_at

### Snapshot Rules

1. The initial state must be stored before the first interaction.
2. A new snapshot is created only after an accepted state transition or an explicitly defined checkpoint.
3. Previous snapshots must remain accessible.
4. Every snapshot must identify its originating transitions.
5. Snapshots must be reproducible from the relevant event history and rule versions.
6. Restoring an earlier snapshot must create an auditable restoration event rather than silently deleting later history.

---

## 11. Handling Uncertainty and Contradictions

The simulation must represent uncertainty explicitly.

Examples:

- The client reports willingness during one exercise but avoids a similar situation later.
- The client agrees to homework but does not attempt it.
- The client expresses greater clarity about values but remains uncertain about a specific action.
- The client shares personal information and subsequently feels uncomfortable about the disclosure.

These patterns are not necessarily errors or inconsistencies.

### Handling Rules

1. Preserve contradictory evidence.
2. Do not force monotonic improvement across sessions.
3. Do not assume temporary engagement represents lasting change.
4. Keep observed statements separate from inferred psychological processes.
5. Use requires_review when available evidence cannot support a clear transition.
6. Allow later sessions to revise prior hypotheses without rewriting historical transcripts.

Uncertainty must remain visible in internal records and relevant reports.

---

## 12. Idempotency and Event Processing

The system must prevent the same event from being applied multiple times.

Each processed transition must be associated with unique evidence and a unique processing identity.

The initial implementation should support:

- Duplicate event detection.
- Duplicate transition detection.
- Ordered event processing.
- Event processing status.
- Error logging.
- Safe retry of failed operations.

Reprocessing an event must not cause repeated state changes.

---

## 13. Reproducibility and Versioning

Each state transition must be traceable to:

- Case version.
- State schema version.
- Transition rule version.
- Event extraction version.
- Model identifier, when model-assisted extraction is used.
- Prompt version, when applicable.
- Relevant transcript messages.

Given the same initial state, accepted event history, and deterministic rule configuration, the system should be able to reconstruct the same state snapshots.

Model-assisted extraction may introduce variability. The original extraction output and the final validation decision must therefore be retained separately.

---

## 14. Safety Boundaries

Safety-related information requires separate handling from ordinary state transitions.

The system must:

1. Preserve safety-related statements accurately.
2. Avoid assigning safety status solely from general emotional language.
3. Use explicitly defined safety scenarios and response procedures.
4. Never assume that the absence of a detected safety event establishes the absence of risk.
5. Avoid presenting synthetic safety handling as validated clinical risk assessment.
6. Record safety protocol activation as a separate auditable event.

The initial synthetic case safety baseline must not be generalized to real people or other synthetic cases.

---

## 15. Initial Implementation Scope

The first implementation of the State Transition System will support:

- Six initial ACT simulation variables.
- A structured event schema.
- Candidate event extraction.
- A small versioned transition rule registry.
- Deterministic range and evidence-reference validation.
- Accepted and rejected transition records.
- Immutable state history.
- Duplicate event prevention.
- Basic audit logging.

Advanced uncertainty calibration, complex temporal reasoning, and learned transition policies are outside the initial implementation scope.

---

## 16. Open Design Questions

The following questions require further design and testing:

- What behavioral anchors define each value of each state variable?
- Which event types are suitable for rule-based extraction?
- Which event types require model-assisted interpretation?
- How should multiple pieces of contradictory evidence be weighted?
- How should uncertainty be represented consistently?
- How should evidence spans be linked to exact transcript text?
- How should state history be reconstructed after interrupted sessions?
- How should transition rules be validated by qualified ACT experts?
- How should inter-case and inter-model consistency be evaluated?

---

**End of Document**