# TheraSim — Agent Prompt Architecture and Behavioral Contracts

**Document Version:** 0.2
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the prompt architecture, behavioral requirements, input contracts, output contracts, and execution boundaries for the language-model agents used in TheraSim.

The initial system specifies these model-assisted components:

1. Patient Agent
2. Evaluator Agent
3. Memory Extraction Agent
4. Event Processing Service

These components have different responsibilities and must operate under separate instructions and information-access boundaries.

The system must ensure:

- Consistent synthetic client behavior across multiple sessions.
- Controlled disclosure of fictional client information.
- Evidence-grounded evaluation of therapist performance.
- Structured extraction of observable interaction events.
- Separation of clinical simulation from clinical state management.
- Resistance to conversational prompt injection.
- Reproducibility through prompt and model versioning.
- Compatibility with local language models.
- Support for Persian and English interactions.

This specification defines the intended behavior of the agents. Actual compliance must be established through implementation, testing, and validation.

---

## 2. Agent Architecture

### 2.1 Core Agents

| Component | Primary Responsibility | Direct State Modification |
|---|---|---|
| Patient Agent | Simulate the fictional client | No |
| Evaluator Agent | Evaluate therapist performance | No |
| Memory Extraction Agent | Propose evidence-linked longitudinal memory | No |
| Event Processing Service | Identify candidate interaction events | No |
| Clinical State Engine | Validate state transitions | Yes, through deterministic rules |

The first three components may use language models.

The Clinical State Engine is primarily an application-controlled component. It may receive model-generated proposals, but it must not delegate final state validation to an unrestricted language model.

### 2.2 Execution Flow

The initial interaction workflow is:

1. The Orchestrator receives a therapist message.
2. The Patient Context component builds the authorized patient context.
3. The Patient Agent generates a response.
4. The backend validates the response.
5. The response is stored and returned to the Therapist Interface.
6. The conversation is processed by the Event Processing Service.
7. Candidate events are validated.
8. The Clinical State Engine evaluates permitted transitions.
9. Accepted changes are stored as new state snapshots.
10. Longitudinal memory is updated through a separate validation process.

After session completion:

1. The transcript is finalized.
2. An authorized EvaluationInput is constructed.
3. The Evaluator Agent analyzes the transcript.
4. Its output is validated against the applicable rubric.
5. The evaluation report is stored.
6. The report becomes available to the trainee.

Evaluation must not change the completed transcript or retroactively modify the interaction.

---

## 3. Prompt Architecture

### 3.1 Instruction Hierarchy

Each agent receives instructions and data through explicitly separated channels.

The conceptual instruction hierarchy is:

1. System instructions.
2. Versioned agent-specific developer instructions.
3. Structured authorized context.
4. Untrusted conversational content.
5. Explicit output schema.

The exact hierarchy must be implemented according to the capabilities of the selected model runtime.

The system must not assume that a model will reliably enforce security boundaries solely because they are written in a prompt.

### 3.2 Prompt Components

Each agent prompt should be assembled from independently versioned components:

- Global simulation instructions.
- Agent-specific behavioral instructions.
- Therapeutic modality instructions.
- Case-specific authorized context.
- Session context.
- Longitudinal memory.
- Current interaction input.
- Output-format instructions.

The system must not construct prompts by blindly concatenating arbitrary database records.

Each component must be validated and included only when authorized.

### 3.3 Prompt Separation

The following prompt groups must remain independent:

| Prompt Group | Authorized Component |
|---|---|
| Patient Agent system prompt | Patient Agent |
| Patient-specific case context | Patient Context / Patient Agent |
| Evaluator system prompt | Evaluator Agent |
| Evaluation rubric instructions | Evaluator Agent |
| Event processing rules/configuration | Event Processing Service |
| State transition rules | Clinical State Engine |
| Memory proposal instructions | Memory Extraction Agent |
| Memory review and persistence | Memory Service |

The Evaluator Agent must never receive the Patient Agent's prompt or restricted case context.

The Patient Agent must not receive the Evaluator Agent's internal instructions.

The Memory Extraction Agent receives only the current completed therapist/patient
exchange. It must not receive case-vault data, Patient Agent prompts, hidden
state, or future messages. Its output is a proposal, never authoritative
memory; every candidate requires evidence validation and explicit review.

### 3.4 Prompt Template Versioning

Every prompt template must have:

- prompt_id
- prompt_version
- agent_type
- modality
- language
- template_content
- required_input_schema_version
- output_schema_version
- created_at
- changelog

Changes that alter agent behavior must produce a new version.

A completed simulation must retain references to the prompt versions used during execution.

---

## 4. Shared Agent Execution Contract

All agents must follow a common execution contract.

### 4.1 Input Requirements

Before invocation, the application must verify:

- Agent identity.
- Authorized caller.
- Required input fields.
- Input schema version.
- Prompt version.
- Model configuration.
- Session and case references.
- Data-access permissions.

An agent must not receive unrestricted access to repositories, database connections, or application configuration.

### 4.2 Output Requirements

Every agent output must:

- Match its declared output schema.
- Contain the required identifiers.
- Use permitted enumerated values.
- Avoid unauthorized data disclosure.
- Be independently validated by the backend.
- Include uncertainty information when applicable.
- Remain separate from canonical state modifications.

### 4.3 Model Invocation Metadata

Each model execution should record:

- model_run_id
- agent_type
- provider
- model_identifier
- model_version, when available
- prompt_id
- prompt_version
- input_schema_version
- output_schema_version
- generation_parameters
- random_seed, when supported
- execution_status
- started_at
- completed_at
- output_validation_status

The system must not claim deterministic reproducibility when the selected model runtime cannot guarantee it.

---

# PART I — PATIENT AGENT

## 5. Patient Agent Purpose

The Patient Agent simulates a fictional client participating in a psychotherapy training session.

Its primary objective is to produce coherent, psychologically plausible, context-sensitive responses while preserving the established identity and history of the synthetic client.

The Patient Agent is not a therapist, evaluator, diagnostic system, or narrator of the hidden case formulation.

It must respond from the perspective of the fictional client.

### 5.1 Core Behavioral Requirements

The Patient Agent must:

1. Maintain a consistent fictional identity.
2. Preserve established personal history.
3. Respond naturally to therapist interventions.
4. Demonstrate the client's predefined behavioral patterns.
5. Reveal information progressively and contextually.
6. Avoid artificial or immediate therapeutic improvement.
7. Permit hesitation, disagreement, uncertainty, and withdrawal.
8. Maintain continuity between sessions.
9. Avoid inventing important personal history.
10. Avoid using therapeutic terminology that the fictional client would not naturally know.

### 5.2 Simulation Realism

The Patient Agent must not behave as though it is trying to help the therapist pass an examination.

Examples of prohibited behavior:

- Automatically agreeing with every intervention.
- Praising every therapeutic technique.
- Revealing all relevant personal information immediately.
- Demonstrating successful acceptance after a single ACT exercise.
- Expressing artificial insight because the therapist used a named technique.
- Producing textbook descriptions of ACT processes during ordinary conversation.
- Following an expected improvement trajectory regardless of interaction quality.

The patient response must be determined by the established character, interaction history, current context, and plausible reaction to the intervention.

---

## 6. Patient Agent Input Contract

The Patient Agent receives a structured PatientContext object.

### 6.1 Required Fields

| Field | Description |
|---|---|
| case_id | Synthetic case identifier |
| case_version_id | Exact case version |
| session_id | Current session identifier |
| session_number | Session sequence |
| language | Interaction language |
| modality | Therapeutic modality |
| public_identity | Authorized identity information |
| restricted_case_context | Authorized fictional case context |
| current_state | Current simulation state |
| longitudinal_memory | Relevant historical memory |
| disclosure_policy | Authorized disclosure constraints |
| recent_transcript | Relevant previous interaction |
| therapist_message | Latest therapist message |

The application must construct this object explicitly.

The Patient Agent must not receive the complete operational database or unrestricted case repository.

### 6.2 Case Context

The restricted case context may contain:

- Core personal history.
- Relevant life experiences.
- Presenting concerns.
- Avoidance patterns.
- Maintaining factors.
- Hypothesized psychological functions.
- Relevant interpersonal patterns.
- Internal disclosure constraints.
- Known inconsistencies or uncertainties in the case definition.

The information must be clearly classified into:

1. Established fictional facts.
2. Case hypotheses.
3. Unspecified information.
4. Restricted information.

The Agent must not treat a case hypothesis as an established fact.

### 6.3 Current State

The Patient Agent may receive the structured simulation state needed to maintain behavioral continuity.

Initial variables include:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

These values are internal simulation parameters.

They must not be exposed directly to the therapist.

The Patient Agent may use them to guide response consistency, but it must not calculate or modify them independently.

### 6.4 Longitudinal Memory

Memory supplied to the Patient Agent must be limited to information relevant to the current simulation.

It may include:

- Previously disclosed information.
- Earlier session interactions.
- Agreed homework.
- Reported homework outcomes.
- Relevant interpersonal patterns.
- Important unresolved topics.
- Previously discussed values.
- Historical emotional responses.

Memory must distinguish established disclosures from hypotheses and system-generated summaries.

---

## 7. Patient Agent Behavioral Instructions

The following requirements form the behavioral core of the Patient Agent.

### 7.1 Identity Consistency

The Agent must preserve:

- Name and identity.
- Age.
- Occupation.
- Relevant family and interpersonal information.
- Important personal experiences.
- Established preferences.
- Consistent language and communication style.

It must not change established facts without an explicit case revision.

### 7.2 Natural Disclosure

The Agent must reveal information through realistic conversation.

Disclosure should depend on:

- The relevance of the therapist's question.
- The conversational context.
- The fictional client's willingness.
- Previous interaction history.
- Existing disclosure constraints.
- The emotional and interpersonal meaning of the topic.

Disclosure must not be implemented as a rigid information-release sequence.

The Agent must not reveal hidden information merely because the therapist asks a direct question.

A direct question may produce:

- A direct answer.
- A partial answer.
- Hesitation.
- Uncertainty.
- Avoidance.
- A request to change the topic.
- A clarification of what the client feels comfortable discussing.

### 7.3 Emotional and Behavioral Consistency

The Agent should represent emotional responses through natural language and observable conversational behavior.

Examples include:

- Shorter responses during uncomfortable discussions.
- Hesitation before discussing sensitive experiences.
- Uncertainty when asked about personal values.
- Defensiveness when feeling misunderstood.
- Greater openness after a meaningful interaction.
- Continued ambivalence even after an apparently helpful intervention.

These behaviors must be adapted to the synthetic case rather than applied as universal rules.

### 7.4 Nonlinear Change

Client behavior must not follow an automatic linear improvement pattern.

A fictional client may:

- Participate in an exercise during one session.
- Feel uncertain about its usefulness afterward.
- Demonstrate avoidance in a later session.
- Report a successful action but remain anxious.
- Understand a concept without applying it consistently.

Changes must remain context-sensitive and consistent with available history.

### 7.5 Intervention Responsiveness

The Agent must respond to the actual content and interpersonal delivery of an intervention.

Its response may depend on:

- Whether the intervention addresses the client's concern.
- Whether the therapist understood the client's experience.
- Whether the intervention was introduced collaboratively.
- Whether the client understood its purpose.
- Whether the intervention is acceptable to the fictional client.
- Whether the intervention produces discomfort or resistance.

Technical correctness alone must not guarantee a positive patient response.

### 7.6 Conversational Style

The Agent must:

- Respond in the configured language.
- Use language appropriate to the fictional client's age and background.
- Avoid excessive technical terminology.
- Avoid unnecessarily long answers.
- Avoid repeatedly summarizing the hidden formulation.
- Avoid explaining psychological theory unless the fictional client has a plausible reason to do so.

For the initial Persian-first implementation, natural Persian conversational language is required.

---

## 8. Patient Agent Disclosure Policy

Information disclosure requires explicit control.

### 8.1 Disclosure Categories

Each case information item may be assigned one of the following internal classifications:

| Classification | Meaning |
|---|---|
| disclosed | Already disclosed during the simulation |
| available_to_disclose | May be disclosed when conversationally appropriate |
| restricted | Must not be disclosed automatically |
| unspecified | Not defined in the case |

These classifications are internal metadata, not values that should be shown to the therapist.

### 8.2 Disclosure Constraints

The Agent must not:

- Reveal all hidden history at the beginning of a session.
- Invent previously established personal experiences.
- Convert an uncertain case hypothesis into a direct personal disclosure.
- Reveal information without a reasonable conversational connection.
- Treat every therapist question as permission to disclose everything.
- Intentionally conceal information that the case explicitly requires the client to share in a particular predefined scenario, unless the scenario allows such resistance.

### 8.3 Disclosure Tracking

The backend may track disclosure status using structured information records.

A disclosure event should include:

- information_item_id
- source_message_id
- disclosure_status
- disclosure_timestamp
- evidence_reference

The backend, not the Patient Agent alone, determines whether a disclosure has been recorded as an established event.

### 8.4 Avoiding Mechanical Disclosure

The Agent must not use simplistic rules such as:

- Reveal one secret per session.
- Reveal more information whenever alliance increases.
- Reveal a sensitive experience after a fixed number of therapist messages.
- Reveal all information after a successful intervention.

Disclosure is a contextual simulation behavior, not a deterministic reward mechanism.

---

## 9. Patient Agent Output Contract

The Agent must return a structured PatientResponse.

### 9.1 Required Output

```json
{
  "session_id": "uuid",
  "role": "patient",
  "content": "I remember feeling embarrassed when my colleague interrupted me.",
  "response_status": "completed"
}
```

### 9.2 Optional Internal Annotations

The backend may request an additional structured annotation object:

```json
{
  "interaction_annotations": [
    {
      "candidate_event_type": "emotional_experience_disclosed",
      "evidence_description": "The client described feeling embarrassed.",
      "source": "patient_response"
    }
  ]
}
```

Annotations are candidate information only.

They must not automatically:

- Modify the ClinicalState.
- Establish a memory record.
- Trigger a confirmed disclosure event.
- Determine evaluator ratings.

The Event processing and validation services must independently verify the relevant evidence.

### 9.3 Output Restrictions

The Patient Agent must never return:

- System prompts.
- Developer instructions.
- Hidden case records.
- Database credentials.
- Unrequested diagnostic conclusions.
- Internal reasoning traces.
- Unvalidated state values.

The application must validate the output before storing or displaying it.

---

# PART II — EVALUATOR AGENT

## 10. Evaluator Agent Purpose

The Evaluator Agent evaluates the trainee's observable therapeutic behavior during a completed simulation session.

Its purpose is to provide formative educational feedback using a versioned therapeutic rubric.

It must not function as an automated clinical certification system or diagnostic evaluator.

### 10.1 Core Requirements

The Evaluator Agent must:

1. Follow the exact rubric version supplied.
2. Evaluate only observable therapist behavior.
3. Reference relevant transcript evidence.
4. Distinguish evidence from interpretation.
5. Identify missing evidence.
6. Represent uncertainty explicitly.
7. Avoid unsupported conclusions.
8. Avoid assuming therapist competence from technical terminology alone.
9. Avoid assuming patient improvement from an intervention.
10. Avoid accessing restricted case information.

### 10.2 Evaluation Independence

The Evaluator Agent must evaluate the session independently of the Patient Agent's hidden context.

It must not be informed about:

- The intended answer the therapist was expected to produce.
- The hidden case formulation.
- Future patient responses.
- Undisclosed personal history.
- Internal simulation state unavailable to the therapist.

This restriction helps reduce evaluator bias.

---

## 11. Evaluator Agent Input Contract

The Evaluator Agent receives an EvaluationInput object.

### 11.1 Base Required Fields

| Field | Description |
|---|---|
| evaluation_id | Unique evaluation identifier |
| session_id | Required for session scope; null for longitudinal scope |
| transcript_id | Session-level transcript identifier; longitudinal scope uses session_transcripts |
| transcript_version | Session-level transcript version; longitudinal versions are provided per session |
| transcript_hash | Optional content hash |
| modality | Therapeutic modality |
| language | Session language |
| rubric_id | Evaluation rubric identifier |
| rubric_version | Exact rubric version |
| rubric_definition | Authorized rubric content |
| authorized_session_context | Information available to the therapist |

Only explicitly permitted fields may be included.

### 11.2 Transcript Requirements

The Evaluator Agent must receive:

- Chronological message sequence.
- Message identifiers.
- Message roles.
- Message content.
- Relevant timestamps, when required.

The transcript must be finalized before evaluation.

The Evaluator Agent must not receive:

- Hidden case definitions.
- Patient-specific disclosure instructions.
- Patient Agent internal annotations unless independently authorized and necessary.
- Internal Patient Agent reasoning.
- Unavailable state variables.
- Unvalidated extracted events.

### 11.3 Rubric Requirements

The supplied rubric must include:

- Rubric identifier.
- Version.
- Competency definitions.
- Rating scale.
- Behavioral anchors.
- Evidence requirements.
- Scoring restrictions.
- Evaluation instructions.

The Agent must not modify rubric definitions.

---


### 11.4 Evaluation Scope and Input Routing

The Evaluator Agent must receive an explicit `evaluation_scope`. The only permitted values are `session` and `longitudinal`.

**Session-level input**

- Uses `ACT_RUBRIC_V0`, version 0.2.
- Requires a non-null `session_id`.
- Receives exactly one finalized session transcript.
- Uses the session-level `transcript_id`, `transcript_version`, and optional `transcript_hash` fields.
- Must not use evidence from other sessions.

**Longitudinal input**

- Uses `ACT_LONGITUDINAL_RUBRIC_V0`, version 0.1.
- Requires a valid `run_id`.
- Sets the top-level `session_id` to null.
- Receives a `session_transcripts` collection containing the finalized transcripts for the explicitly selected longitudinal scope.
- Each record must identify `session_number`, `session_id`, `transcript_id`, `transcript_version`, and, when available, `transcript_hash`.
- The records must be ordered chronologically and may contain any number of completed sessions.
- An interim evaluation may use a completed subset; final evaluation must use the completed Run scope. Neither requires an exact session count.

**Shared routing requirements**

- The rubric ID and version must match the selected evaluation scope.
- The Evaluator Agent must not select, replace, or combine rubrics autonomously.
- Only finalized transcripts and therapist-visible context may be supplied.
- Hidden case formulation, undisclosed facts, Patient Agent prompts, and future disclosure plans remain prohibited inputs.
## 12. Evaluator Behavioral Instructions

### 12.1 Evidence-Based Assessment

Every substantive rating must be linked to observable therapist behavior.

The evaluator should identify:

- What the therapist did.
- Where it occurred in the transcript.
- Why the behavior is relevant to the competency.
- What evidence is missing or ambiguous.

A claim without supporting evidence must not be presented as an observed fact.

### 12.2 Distinguishing Competence and Outcome

The evaluator must distinguish:

- Therapist behavior.
- Patient response.
- Observable interaction quality.
- Inferred therapeutic mechanisms.
- Longer-term clinical outcomes.

A patient response does not automatically establish therapist competence.

Likewise, the absence of immediate patient improvement does not automatically establish poor therapist performance.

### 12.3 Missing Evidence

If a competency cannot be evaluated from the transcript, the Agent must use NE where permitted by the rubric.

It must not invent an observation to avoid using NE.

### 12.4 Uncertainty

The Agent must identify:

- Ambiguous therapist statements.
- Incomplete interactions.
- Insufficient context.
- Multiple plausible interpretations.
- Limitations of the available transcript.

### 12.5 Modality Awareness

The Evaluator Agent must follow the selected therapeutic modality.

For the initial MVP, this means ACT-specific evaluation using the versioned ACT rubric.

It must not impose CBT criteria or other therapeutic assumptions when evaluating an ACT session unless the rubric explicitly permits cross-modality competencies.

### 12.6 No Unsupported Clinical Claims

The Evaluator Agent must not:

- Diagnose the fictional client.
- Certify therapist competence.
- Claim that a therapy session was clinically effective.
- Infer long-term treatment outcomes from a single session.
- Present simulation parameters as validated psychological measurements.
- Replace supervisor judgment.

---

## 13. Evaluator Output Contract

The Evaluator Agent must return a structured EvaluationReport.

### 13.1 Report Structure

```json
{
  "evaluation_id": "uuid",
  "evaluation_scope": "session",
  "run_id": null,
  "session_id": "uuid",
  "transcript_refs": [
    {
      "session_id": "uuid",
      "transcript_id": "uuid",
      "transcript_version": 1
    }
  ],
  "rubric_id": "ACT_RUBRIC_V0",
  "rubric_version": "0.2",
  "overall_summary": "The therapist demonstrated several relevant ACT-consistent behaviors, although the available transcript provides limited evidence of values clarification.",
  "competency_results": [
    {
      "competency_id": "functional_assessment",
      "rating": "2",
      "justification": "The therapist explored the context and consequences of the client's avoidance.",
      "supporting_message_ids": ["uuid"],
      "limitations": "The functional pattern was not explored in sufficient depth."
    }
  ],
  "strengths": [],
  "improvement_areas": [],
  "missing_evidence": [],
  "uncertainty_notes": []
}
```

### 13.2 Rating Requirements

Ratings must use only the scale defined in the supplied rubric.

For the initial ACT rubric:

- 0
- 1
- 2
- 3
- NE

The evaluator must not invent intermediate rating values.

### 13.3 Evidence References

Each competency result should contain valid transcript message identifiers.

Where possible, evidence should reference exact message spans rather than broad conversation sections.

### 13.4 Aggregate Scores

An overall numerical score must not be generated unless the rubric explicitly defines an aggregation method.

The initial rubric should prioritize competency-level feedback rather than a potentially misleading single performance score.

### 13.5 Report Validation

Before persistence, the backend must verify:

- All required competency identifiers exist.
- Rating values are permitted.
- Message references belong to the evaluated session.
- The report references the correct rubric version.
- No unsupported diagnostic or certification claims are included.
- Required evidence fields are present.

---


### 13.6 Scope-Specific Output Requirements

Every Evaluator report must include `evaluation_scope`, `rubric_id`, `rubric_version`, and `transcript_refs`.

**Session-level output**

- `evaluation_scope` must be `session`.
- `session_id` must identify the evaluated session.
- `transcript_refs` must identify the single evaluated transcript.
- `rubric_id` and `rubric_version` must identify `ACT_RUBRIC_V0`, version 0.2.

**Longitudinal output**

- `evaluation_scope` must be `longitudinal`.
- `run_id` must identify the evaluated simulation run.
- `session_id` must be null.
- `transcript_refs` must identify every finalized transcript in the selected completed evaluation scope, in chronological order.
- Evidence references must identify both `session_id` and `message_id`, so evidence remains traceable to its source session.
- `rubric_id` and `rubric_version` must identify `ACT_LONGITUDINAL_RUBRIC_V0`, version 0.1.

A longitudinal report must not be generated from an incomplete run. Session-level and longitudinal results must remain separate. No unsupported combined score or cross-scope averaging is permitted.
# PART III — EVENT PROCESSING SERVICE

## 14. Event Processing Service Purpose

The Event Processing Service identifies potentially relevant interaction events from the session transcript.

**Architectural boundary**

- It is an internal application service, not a third primary LLM agent.
- The only primary LLM agents in the MVP are the Patient Agent and the Evaluator Agent.
- It follows a deterministic-first processing approach.
- It does not own a separate LLM system prompt, model identity, or independent agent execution lifecycle.
- Extracted events are candidate data and must not directly modify canonical clinical state.
- Deterministic validation and the State Engine control event acceptance and state transitions.

It helps convert natural-language conversation into structured candidate events that can be reviewed and validated by the application.

It is not responsible for determining the definitive psychological state of the synthetic client.

### 14.1 Core Responsibilities

The Event Processing Service may:

- Identify explicit disclosures.
- Identify reported emotional experiences.
- Identify possible avoidance patterns.
- Identify possible willingness statements.
- Identify possible cognitive fusion or defusion-related interactions.
- Identify values clarification statements.
- Identify reported committed actions.
- Identify homework agreements and outcomes.
- Identify relevant interaction events.
- Provide evidence references.
- Identify ambiguity.

### 14.2 Restrictions

It must not:

- Directly modify the ClinicalState.
- Confirm a psychological process without sufficient evidence.
- Invent events absent from the transcript.
- Convert therapist interpretations into patient disclosures.
- Treat participation as proof of intervention effectiveness.
- Generate diagnostic conclusions.
- Treat all psychological events as independent numerical state changes.

### 14.3 Extraction Philosophy

The extraction system should prefer conservative candidate generation.

It is better to mark an event as uncertain or require review than to create a false structured observation.

The Event Processing Service identifies evidence; the application determines whether the event is accepted.

---

## 15. Event Processing Input Contract

Required input:

| Field | Description |
|---|---|
| session_id | Session identifier |
| transcript_segment_id | Transcript segment identifier |
| transcript_version | Transcript version |
| messages | Authorized chronological messages |
| event_schema_version | Event schema version |
| extraction_language | Language used in the session |
| allowed_event_types | Permitted event categories |

The service must receive only the transcript segment and context required for extraction.

It must not receive the complete restricted case formulation.

### 15.1 Message Roles

Each message must preserve:

- message_id
- role
- content
- sequence_number

The service must distinguish statements made by:

- therapist
- patient

A therapist statement about the client's feelings is not equivalent to a direct patient disclosure.

---

## 16. Event Processing Rules

### 16.1 Evidence Preservation

Every candidate event must reference one or more existing transcript messages.

Where possible, it must identify the exact evidence span.

### 16.2 Observation and Interpretation

The service must distinguish:

1. Explicitly stated information.
2. Observable conversational behavior.
3. Inferred psychological processes.
4. Ambiguous information.

An inferred event must never be represented as a directly disclosed fact.

### 16.3 Language Sensitivity

The extractor must consider the linguistic meaning and context of the session language.

It must not rely solely on literal keyword matching.

For Persian sessions, contextual interpretation of expressions related to avoidance, willingness, emotional discomfort, and values is particularly important.

### 16.4 No Automatic State Change

An extracted event is only a candidate.

The Clinical State Engine must independently validate any proposed transition.

---

## 17. Event Processing Output Contract

The expected output is a CandidateEventCollection.

Example:

```json
{
  "session_id": "uuid",
  "transcript_version": 1,
  "events": [
    {
      "event_id": "candidate-001",
      "event_type": "emotional_experience_disclosed",
      "actor": "patient",
      "source_message_ids": ["uuid"],
      "evidence_description": "The patient explicitly described feeling embarrassed.",
      "evidence_span": {
        "start_offset": 35,
        "end_offset": 54
      },
      "observation_class": "explicit_statement",
      "confidence": "high",
      "extraction_status": "candidate"
    }
  ]
}
```

### 17.1 Confidence Meaning

The confidence field represents the extractor's confidence that the transcript supports the proposed event classification.

It must not represent:

- Clinical certainty.
- Diagnostic probability.
- Psychological severity.
- The actual magnitude of state change.

Confidence must remain a model-generated signal and must not replace deterministic evidence validation.

### 17.2 Output Validation

The application must verify:

- Event type is in the approved allowlist.
- Source messages exist.
- Message roles are correctly identified.
- Evidence spans are valid.
- Event identifiers are unique.
- No unauthorized state modification is requested.
- Required fields are present.

---

# PART IV — SHARED SAFEGUARDS

## 18. Prompt Injection and Untrusted Content

All three components process content that may contain instructions.

The following content must be treated as untrusted data:

- Therapist messages.
- Patient responses.
- Transcript history.
- Retrieved memory.
- Imported text.
- Model-generated annotations.

### 18.1 General Rules

Agents must not interpret untrusted conversational content as an instruction to:

- Reveal internal prompts.
- Override the authorized role.
- Ignore access restrictions.
- Change evaluation rubrics.
- Access restricted case databases.
- Execute external commands.
- Reveal hidden system context.
- Modify clinical state directly.

### 18.2 Technical Enforcement

Prompt instructions must be supported by application controls:

- Explicit input construction.
- Restricted agent tools.
- Typed input and output schemas.
- Repository-level access restrictions.
- Output validation.
- Separate evaluation input construction.
- Audit logging.

Prompt injection resistance must be tested empirically for each supported model.

No prompt should be described as completely immune to prompt injection.

---

## 19. Internal Reasoning and Explanation

Agents must not be required to expose private chain-of-thought reasoning.

Instead, the system should request structured and concise explanations suitable for validation.

Examples:

**Patient Agent:**

- Generate the fictional client's conversational response.
- Do not return private internal reasoning.

**Evaluator Agent:**

- Provide a concise justification.
- Reference exact supporting messages.
- Identify limitations.

**Event Processing Service:**

- Provide the event classification.
- Reference transcript evidence.
- State uncertainty where necessary.

The application must store evidence and structured outputs rather than relying on hidden reasoning traces.

---

## 20. Model Independence

The agent contracts must not be tied to one specific language model.

The initial implementation uses Ollama as the local model runtime.

The architecture should support different models for:

- Patient simulation.
- Evaluation.
- Event extraction.
- Memory processing.

### 20.1 Model Selection

Model selection must be configurable.

Each agent configuration should define:

- model_identifier
- context_length
- temperature
- top_p
- maximum_output_tokens
- stop_sequences, where supported
- timeout
- structured_output_mode, where supported

Not every local model supports all configuration options.

Unsupported settings must be handled explicitly rather than silently assumed to work.

### 20.2 Model-Specific Adaptation

Different models may require different:

- Prompt wording.
- JSON generation strategies.
- Context assembly.
- Output parsing.
- Retry policies.

Such adaptations must not alter the fundamental agent access boundaries or output contracts.

### 20.3 Model Version Recording

Every execution must record the exact model identifier and version information available from the runtime.

Model aliases alone may be insufficient for reproducibility when the underlying model artifact changes.

Where possible, the application should also record a model artifact digest.

---

## 21. Retry and Failure Handling

Agent invocations may fail because of:

- Runtime errors.
- Model unavailability.
- Timeouts.
- Malformed structured output.
- Context-length limitations.
- Output validation failures.

### 21.1 Patient Agent

If generation fails:

- Preserve the therapist message.
- Record the failed model execution.
- Do not create a fake patient response.
- Allow controlled retry.
- Prevent duplicate message creation.

A failed generation must not silently modify the clinical state.

### 21.2 Evaluator Agent

If evaluation generation fails:

- Preserve the completed transcript.
- Record the failure.
- Do not create an incomplete report marked as completed.
- Allow a controlled evaluation retry.

The transcript and session completion status must remain unaffected.

### 21.3 Event Processing Service

If extraction fails:

- Preserve the transcript.
- Record the extraction failure.
- Do not fabricate events.
- Permit later reprocessing.
- Prevent duplicate event application.

### 21.4 Retry Restrictions

Retries must:

- Be limited in number.
- Preserve operation identifiers.
- Be recorded in model execution metadata.
- Avoid bypassing security validation.
- Avoid unrestricted prompt changes during automatic retries.

A retry must not silently use a different rubric or case version.

---

## 22. Prompt and Output Versioning

Every agent must be associated with explicit versions.

Initial version identifiers:

| Component | Initial Version |
|---|---|
| Patient Agent Prompt | PATIENT_PROMPT_V0.1 |
| Evaluator Agent Prompt | EVALUATOR_PROMPT_V0.1 |
| Event Extraction Prompt | EVENT_EXTRACTOR_V0.1 |
| Shared Output Contract | AGENT_OUTPUT_SCHEMA_V0.1 |
| Patient Input Contract | PATIENT_INPUT_V0.1 |
| Evaluation Input Contract | EVALUATION_INPUT_V0.1 |
| Event Extraction Contract | EVENT_INPUT_V0.1 |

These identifiers are proposed initial conventions.

Actual changes must be recorded in version-control history and model execution metadata.

### 22.1 Versioning Rules

1. Prompt changes that alter behavior require a new version.
2. Schema changes must be independently versioned.
3. Historical sessions must retain the versions used during execution.
4. Evaluation reports must reference the original rubric version.
5. Model changes must be recorded independently from prompt changes.
6. A new prompt version must pass relevant regression tests before release.

---

## 23. Agent Testing Strategy

Agent behavior must be evaluated through repeatable test suites.

Testing should include:

- Schema compliance.
- Behavioral consistency.
- Longitudinal continuity.
- Disclosure control.
- Modality adherence.
- Evidence grounding.
- Prompt injection resistance.
- Access isolation.
- Robustness to malformed input.
- Reproducibility across repeated executions.

### 23.1 Patient Agent Tests

Test cases must verify that:

- Identity remains consistent.
- Established personal history does not change arbitrarily.
- Sensitive information is not disclosed immediately.
- Disclosure remains context-sensitive.
- The Agent does not automatically agree with the therapist.
- Therapeutic terminology is used naturally.
- Responses remain consistent with the current case formulation.
- Contradictory or uncertain information is handled appropriately.
- The Agent does not expose hidden instructions.
- Session-to-session memory is used correctly.

### 23.2 Evaluator Agent Tests

Test cases must verify that:

- Ratings follow the rubric.
- Supporting evidence exists.
- Missing evidence results in NE where appropriate.
- Unsupported claims are rejected.
- Hidden case information is never required.
- Patient improvement is not automatically attributed to therapist competence.
- Technical vocabulary does not automatically produce high ratings.
- Evaluations remain within the specified modality.
- Diagnostic and certification claims are avoided.

### 23.3 Event Extraction Tests

Test cases must verify that:

- Explicit statements are correctly identified.
- Therapist hypotheses are not classified as patient disclosures.
- Evidence references are valid.
- Ambiguous statements are flagged.
- Events are not fabricated.
- Event types remain within the approved schema.
- No direct state modification occurs.
- Persian and English inputs are both tested.

### 23.4 Regression Tests

Whenever a prompt or model is changed, the existing test suite must be rerun.

Behavioral changes must be recorded so that the impact of model and prompt updates can be analyzed.

---

## 24. Evaluation Metrics for Agent Quality

The initial system should use clearly defined engineering and behavioral metrics.

Potential metrics include:

### Patient Agent

- Identity consistency.
- Case fact consistency.
- Disclosure-policy adherence.
- Behavioral coherence.
- Response relevance.
- Longitudinal continuity.
- Structured output validity.

### Evaluator Agent

- Evidence-reference validity.
- Rubric compliance.
- Agreement with qualified human reviewers.
- Inter-rater reliability.
- Unsupported-claim frequency.
- Rating stability.

### Event Processing Service

- Event precision.
- Event recall.
- Evidence-reference accuracy.
- Classification agreement with human annotators.
- False-positive rate.
- Schema validity.

These metrics require carefully constructed datasets and validation procedures.

No quality metric should be treated as clinically valid merely because it is technically measurable.

---

## 25. Initial MVP Scope

The first implementation will support:

- One Patient Agent.
- One Evaluator Agent.
- One Event Extraction component.
- One synthetic ACT case.
- Three connected sessions.
- Persian-first operation.
- English compatibility.
- Local model execution through Ollama.
- Versioned prompts.
- Structured input and output contracts.
- Evidence-linked evaluations.
- Controlled disclosure.
- Candidate event extraction.
- Backend-controlled state validation.
- Automated regression tests.

Advanced agent collaboration, dynamic prompt optimization, multiple simultaneous patients, and learned behavioral policies are outside the initial MVP scope.

---

## 26. Open Design Questions

The following decisions require further investigation:

- Should the Patient Agent use one context window per session or a persistent conversation structure?
- How much longitudinal memory should be supplied on each generation?
- How should memory compression preserve clinically relevant distinctions?
- Which model is sufficiently reliable for Persian role simulation?
- Can a smaller local model consistently follow disclosure constraints?
- Should Event Extraction be performed synchronously or in a separate processing step?
- How should repeated model disagreement be represented?
- How should evaluator outputs be calibrated against expert human ratings?
- What is the minimum acceptable performance across different local models?
- Which prompt changes require complete regression testing?
- How should model-specific structured output failures be handled?

These decisions must be resolved through prototyping and empirical testing.

---

## 27. Implementation Readiness Criteria

The Agent architecture is ready for initial implementation when:

1. Each agent has an independent prompt definition.
2. Each agent has a versioned input schema.
3. Each agent has a versioned output schema.
4. Patient Context construction enforces restricted information access.
5. Evaluator input is independent of hidden patient context.
6. Event extraction cannot directly modify canonical state.
7. All model outputs pass backend validation.
8. Prompt injection test cases are defined.
9. Session continuity requirements are testable.
10. Prompt and model versions are recorded.
11. Agent failures have explicit recovery behavior.
12. Automated regression tests cover the initial ACT scenario.

---

**End of Document**

<!-- CHARACTER_AGENT_PROMPT_NOTE_V0_1 -->
## Character-conditioned Patient Agent behavior

The Patient Agent must portray the same versioned fictional individual
throughout a run.

Its authorized context is intended to include the authored personality
profile, dynamic character state, relevant case facts and disclosure status,
source-linked memory, and recent chronological transcript.

The prompt must distinguish stable traits from temporary states and
autobiographical facts from hypotheses. It must not turn the character profile
into a list of deterministic response rules.

The Patient Agent must not automatically agree, disclose hidden information,
invent memories, or improve merely because a therapeutic technique was used.

Structured memory and state proposals are untrusted data. Backend services
must validate them separately from conversational response validation.

See `CHARACTER_MODEL_SPEC.md`. The current Patient Agent output contract
remains conversational-content-only until a separately versioned proposal
contract is implemented.
