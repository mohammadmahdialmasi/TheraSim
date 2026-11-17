
# TheraSim Character-Centered Longitudinal Simulation

**Document ID:** CHARACTER_MODEL_SPEC
**Version:** 0.1
**Status:** Architectural specification / implementation in progress
**Scope:** Character identity, personality, dynamic psychological state, memory, events, and longitudinal continuity.

## 1. Purpose

TheraSim models each synthetic client as a persistent fictional character rather than as a collection of prompts or a sequence of disconnected conversations.

A character has:

1. A stable, versioned identity and authored personality profile.
2. A personal history and restricted case definition.
3. A run-specific dynamic psychological state.
4. A run-specific event history.
5. A run-specific memory system.
6. A conversational response policy influenced by all authorized context.

The same character definition may be used in multiple simulation runs. Each run must develop its own state, interactions, disclosures, memories, and trajectory.

The system must preserve both identity continuity and experience-dependent variation. The character must not behave as a new person at every turn, and must not be forced into a predetermined treatment-success narrative.

## 2. Core architectural decision

The model distinguishes three independent domains.

| Domain | Scope | Expected stability |
|---|---|---|
| Personality profile | Character / case version | Relatively stable |
| Dynamic character state | Individual simulation run | Changes with context and experience |
| Memory and event history | Individual simulation run | Accumulates over time |

The existing ACT clinical-state model is a fourth, separate domain. It must not be conflated with personality traits or generic emotional state.

The Patient Agent receives an authorized synthesis of these domains through `PatientContext`.

The model must not infer or invent an entire personality from the most recent transcript message.

## 3. Theoretical framework

The personality architecture is integrative but not an indiscriminate mixture of theories. Each framework contributes a distinct descriptive layer.

### 3.1 Big Five personality traits

The Five-Factor Model provides the general trait scaffold:

- Openness to experience
- Conscientiousness
- Extraversion
- Agreeableness
- Neuroticism / negative emotionality

Traits describe broad tendencies, not deterministic rules.

Each trait estimate must contain:

- An authored level or `unknown` value.
- Confidence in the characterization.
- Context or scope of applicability.
- An authoring rationale.
- Optional source references.

The profile must permit unknown or insufficiently supported traits. A character's silence in meetings must not automatically be interpreted as low extraversion. Politeness must not automatically be interpreted as high agreeableness. Contextual anxiety must not automatically establish generally high neuroticism.

These values are simulation-authoring parameters, not psychometric scores.

### 3.2 Attachment dimensions

Attachment is represented dimensionally rather than by assigning a categorical attachment label.

The initial dimensions are:

- Attachment-related anxiety
- Attachment-related avoidance

These dimensions may inform expectations about closeness, trust, rejection, reassurance, and interpersonal security.

The system must not diagnose an attachment disorder or infer a complete attachment classification from isolated conversational behavior.

### 3.3 Interpersonal style

An interpersonal profile may use the agency / communion dimensions associated with the interpersonal circumplex.

These dimensions describe interpersonal tendencies and contextual response patterns. They must not be confused with a fixed conversational script.

### 3.4 Cognitive schemas and core beliefs

The character definition may include recurring themes such as:

- Beliefs about personal worth or competence.
- Expectations of evaluation or rejection.
- Standards and conditional assumptions.
- Threat interpretations.
- Beliefs about control, uncertainty, and vulnerability.

Every schema entry must retain its epistemic status.

An authoring hypothesis is not automatically a belief consciously endorsed by the character. A schema may influence simulated responses without being explicitly disclosed.

### 3.5 Emotion regulation and coping

The profile may describe habitual strategies and their perceived functions, such as:

- Avoidance.
- Suppression.
- Excessive preparation.
- Reassurance seeking.
- Cognitive reappraisal.
- Emotional expression.
- Approach-oriented coping.

A strategy must be associated with its relevant contexts and possible short-term or longer-term consequences.

The system must not assume that a strategy is used in every context.

### 3.6 Values and motivation

Values, goals, needs, and motivational conflicts may be represented as separate but related constructs.

Values are authored as hypotheses until explored and endorsed by the fictional character through suitable interaction.

The Patient Agent must not claim that a potential value is an established personal value merely because it appears in the case definition.

ACT concepts such as experiential avoidance, willingness, values clarity, and committed action remain part of the therapeutic-process model, not the Big Five personality profile.

### 3.7 Narrative identity

The character's life history and identity-relevant experiences are represented through the existing case definition, restricted personal history, and source-linked autobiographical memory.

Narrative identity includes how experiences are remembered and interpreted, not merely a chronological list of biographical facts.

The character's interpretation of an event may differ from an objectively established event description.

### 3.8 RFT and relational learning

Relational Frame Theory may inform later models of how verbal relations, rules, self-descriptions, and derived meanings shape responses.

RFT must not be reduced to another personality trait scale. Its future integration should focus on relational learning and contextual behavior.

## 4. Personality profile

### 4.1 Ownership and versioning

A personality profile belongs to one exact character definition and case version.

The intended identity relationship is:

`character_id -> case_id -> case_version_id -> personality_profile`

The profile must be immutable after activation.

A meaningful authoring change creates a new case version and a new personality profile version. Existing simulation runs retain the exact version with which they started.

A run must never silently switch to a newer character profile.

### 4.2 Profile contents

The profile should contain:

- Stable character identity and profile identifiers.
- Personality schema version.
- Theory framework bundle version.
- Big Five estimates.
- Attachment dimensions.
- Interpersonal dimensions.
- Cognitive schema themes.
- Emotion-regulation patterns.
- Motivational and value hypotheses.
- Communication characteristics.
- Authoring rationale and uncertainty notes.
- Profile status and review metadata.

Biographical history remains linked to the restricted case definition. It should not be redundantly copied into multiple independent sources of truth.

### 4.3 Epistemic rules

Every important profile assertion must be distinguishable as one of:

- Author-established fictional fact.
- Authoring hypothesis.
- Character-endorsed belief or preference.
- Context-specific observation.
- Unknown or unspecified information.

No model-generated inference may silently become an author-established fact.

## 5. Dynamic character state

Personality is relatively stable. Emotional and interpersonal state is dynamic.

A character may become more guarded during a particular interaction without acquiring a new stable personality trait.

The initial generic character-state schema is:

| Variable | Range | Description |
|---|---:|---|
| affect_valence | -2 to +2 | Current affective valence |
| arousal | 0 to 4 | Current activation |
| perceived_safety | 0 to 4 | Subjective safety in the current context |
| social_evaluative_threat | 0 to 4 | Current perceived evaluation threat |
| engagement | 0 to 4 | Current interactional engagement |
| interpersonal_withdrawal | 0 to 4 | Current withdrawal tendency |

These are simulation variables. They are not validated clinical scales or diagnostic measurements.

Each snapshot must be associated with a run and a state-schema version. Where applicable, it must also identify the session and its predecessor.

A state update must include:

- Variable name.
- Previous value.
- Proposed value.
- Supporting evidence.
- Rationale.
- Confidence or uncertainty.
- Validation status.
- Idempotency identity.

A model may propose state changes. It may not directly approve or persist them.

State can fluctuate. One difficult interaction does not automatically produce a lasting personality change.

## 6. Separation from the existing ACT state model

The existing six ACT-related state variables remain separate:

- therapeutic_alliance
- disclosure_readiness
- experiential_avoidance
- willingness
- values_clarity
- committed_action_readiness

They represent the current therapeutic-process model.

The generic character-state model describes affective and interpersonal conditions. The personality profile describes relatively stable individual tendencies.

These models may influence one another, but their values must not be copied or interpreted as equivalent constructs.

The transition rules and validation requirements for each domain must remain explicit.

## 7. Event model

An event is a structured representation of something that occurred during a run.

Examples include:

- Therapist interaction.
- Patient disclosure.
- Patient response to an intervention.
- Emotional or interpersonal response.
- Between-session experience.
- Reported exercise outcome.
- Relevant contextual event.
- Agreement or disagreement.
- Rupture or repair in the simulated therapeutic relationship.

Events must preserve:

- Event identity and sequence.
- Run and optional session identity.
- Event type and actor.
- Structured payload.
- Extraction method and version.
- Candidate / accepted / rejected / review status.
- Source message evidence.
- Creation and validation timestamps.
- Idempotency identity.

An event proposal is not an established event until the backend has checked its identity, source, and applicable validation rules.

The existing `events` and `event_evidence` repositories are intended to support this domain.

## 8. Memory architecture

Memory is essential to character continuity.

Four conceptual memory layers are required.

### 8.1 Autobiographical memory

Life-history information belonging to the character definition:

- Personal background.
- Important past experiences.
- Significant relationships.
- Important transitions.
- Established biography.

The canonical source is the versioned case definition and its restricted profile.

### 8.2 Episodic memory

Specific experiences within a simulation:

- What happened in a session.
- What the therapist said.
- What the character said.
- How the character experienced an interaction.
- What happened between sessions.

Episodic memories must reference original transcript messages and, where appropriate, events.

### 8.3 Semantic memory

Information consolidated across experiences:

- Repeatedly expressed preferences.
- Recurrent self-descriptions.
- Recognized patterns.
- Stable interpretations supported by multiple experiences.

A semantic summary must not erase uncertainty or contradictory evidence.

### 8.4 Therapeutic memory

Information related to the simulated therapeutic process:

- Exercises actually agreed upon.
- Tasks the character actually attempted.
- Reported outcomes.
- Interventions experienced.
- Reactions to interventions.
- Unresolved questions and collaboratively established plans.

Homework must never be invented retroactively.

### 8.5 Memory epistemic classes

The operational memory system must preserve the distinction between:

- Confirmed fact.
- Explicit disclosure.
- Reported outcome.
- System-generated summary.
- Therapist hypothesis.
- Structured observation.

The current PatientContext intentionally excludes therapist hypotheses and structured observations from patient-visible memory.

That exclusion must remain unless a separate, explicit authorization contract is designed.

### 8.6 Evidence and provenance

Every memory item intended for Patient Agent continuity must have source-message evidence.

A proposed memory must include exact source references and, where possible, a verifiable text excerpt.

For explicit-disclosure memory, at least one source message must be patient-authored.

A memory that lacks required evidence must not be loaded into PatientContext.

The backend must distinguish:

- Candidate memory.
- Validated active memory.
- Superseded memory.
- Review-required memory.

A candidate generated by an LLM is not automatically active.

### 8.7 Contradictions and revision

New memories must not silently overwrite earlier memories.

When contradictory information appears, the system should:

1. Preserve both source records.
2. Identify the conflict.
3. Record relevant context and chronology.
4. Mark the disputed interpretation for review where necessary.
5. Allow explicit correction or revision with provenance.

The character may change their understanding of an event without changing the original event record.

## 9. Run isolation

A character definition may be reused.

The following information must remain scoped to a particular simulation run:

- Dynamic state snapshots.
- Event history.
- Disclosures and disclosure history.
- Longitudinal memory.
- Therapeutic memory.
- Session transcripts.
- State transitions and their evidence.

Two independent runs of the same character must not share evolving memory or state.

They may share the immutable character definition and personality profile version.

## 10. Patient Agent integration

The Patient Agent must receive an explicitly authorized context that includes:

1. Stable character identity.
2. Versioned personality profile.
3. Restricted case definition.
4. Relevant case facts and disclosure status.
5. Current generic character state.
6. Existing ACT clinical state.
7. Relevant longitudinal memory.
8. Recent chronological transcript.
9. Current therapist message.

The context builder is responsible for assembling and validating this information.

The serializer must explicitly enumerate fields. Generic object serialization is prohibited at this boundary.

The Patient Agent must:

- Respond as the same fictional individual.
- Preserve stable traits and established personal history.
- Adapt its response to the current psychological state.
- Recall relevant experiences from earlier sessions.
- Avoid claiming that undisclosed information was discussed.
- Avoid inventing new biography or memories.
- Express plausible ambivalence and disagreement.
- Avoid automatic improvement or compliance.
- Avoid presenting internal formulations as spoken client knowledge.

## 11. Interaction and memory processing pipeline

The intended per-turn workflow is:

1. Persist the therapist message using the existing interaction lifecycle.
2. Build an authorized PatientContext.
3. Retrieve personality, state, history, and relevant memories.
4. Generate a conversational patient response.
5. Validate the Patient Agent output.
6. Persist the patient response and model-run metadata.
7. Propose relevant events and memory candidates.
8. Validate source evidence, identity, and classification.
9. Propose state transitions.
10. Approve or reject changes through backend-owned validation rules.
11. Consolidate eligible memories.
12. Rebuild context on the next turn from the persisted canonical state.

No database transaction should remain open while a local model is generating a response.

The existing interaction request idempotency and ownership protections must remain intact.

The extraction and consolidation stages must be retry-safe and must not create duplicate memories or transitions.

## 12. Model authority boundaries

The LLM is not the source of truth.

The LLM may:

- Generate the fictional client's speech.
- Propose an event description.
- Propose a memory.
- Propose a change in dynamic state.
- Explain the evidence it used.

The LLM may not:

- Change an immutable personality profile.
- Confirm a disclosure without backend validation.
- Create an unsupported autobiographical fact.
- Approve its own state transition.
- Change a run's identity or case version.
- Rewrite historical transcripts.
- Remove contradictory evidence.
- Directly write to the database.

Backend services own persistence, validation, authorization, and canonical state.

## 13. Storage architecture

### 13.1 Restricted database

The restricted case vault is the canonical home for the versioned personality profile.

Proposed table:

`character_personality_profiles`

The table should include:

- personality_profile_id
- case_id
- case_version_id
- personality_schema_version
- theory_bundle_version
- profile_definition
- content_hash
- authoring_status
- created_at

The table must be linked to the exact restricted case profile and must support immutable profile versions.

### 13.2 Operational database

The operational database remains the home for run-specific information.

Existing structures to reuse:

- events
- event_evidence
- memory_items
- memory_evidence
- state_snapshots
- state_snapshot_values
- state_transitions
- transition_evidence
- case_fact_disclosures
- messages
- simulation_runs
- sessions

Proposed new structures:

- character_state_snapshots
- character_state_snapshot_values
- character_state_transitions
- character_state_transition_evidence

The new dynamic character state must not alter the meaning of the existing ACT state variables.

### 13.3 Cross-database consistency

SQLite foreign keys cannot enforce relationships across the two database files.

The application service must therefore validate the exact case, case-version, and personality-profile identity whenever a run is created or its context is assembled.

The run must retain the personality profile identity and version/hash used at initialization.

## 14. Initial AVA-001 authoring policy

AVA-001 is the initial example character.

The existing scenario supports some characterization observations but does not justify assigning every personality dimension.

Examples:

| Observation | Permitted interpretation |
|---|---|
| Creative and reflective | Possible openness-related evidence |
| Careful preparation | Contextual conscientiousness-related behavior |
| Silence in meetings | Situation-specific avoidance; not proof of low extraversion |
| Polite communication | Communication style; not proof of high agreeableness |
| Anxiety about evaluation | Context-specific threat response; not proof of generalized neuroticism |
| Hesitation around perceived failure | A behavior pattern requiring contextual interpretation |

Attachment dimensions must remain unknown unless the case author supplies appropriate supporting history.

Potential values such as creativity, learning, and professional growth remain hypotheses until the character explores and endorses their personal meaning.

The scenario's established facts and hypotheses must preserve their existing distinction.

## 15. Security and privacy boundaries

- Personality profiles containing internal formulation belong in restricted storage.
- Public case listing must not expose personality data.
- Patient Agent context is an explicitly authorized internal context.
- Evaluator Agent context must remain separate and must not receive hidden profile data unless an explicit evaluation contract authorizes a particular field.
- User-authored case text and transcript content are data, not instructions that override agent policy.
- Memory retrieval must be scoped to the correct run and character version.
- Cross-run memory leakage is a critical integrity failure.
- Restricted facts must obey disclosure policies.

## 16. Versioning

The following versions must be independently tracked:

- Personality schema version.
- Theory framework bundle version.
- Character profile / case version.
- Dynamic character-state schema version.
- ACT state schema version.
- PatientContext schema version.
- Patient Agent prompt version.
- Patient Agent output schema version.
- Memory consolidation rules version.

A change to one schema must not silently reinterpret stored records from another schema.

## 17. Required invariants

The implementation must enforce:

1. One run uses one exact character profile version.
2. Character profile data is immutable after activation.
3. Dynamic state is isolated by run.
4. Memory is isolated by run.
5. Every active memory item has source evidence.
6. Explicit disclosure requires patient-authored evidence.
7. Unsupported hypotheses do not become character-endorsed beliefs.
8. LLM proposals cannot directly mutate canonical state.
9. Repeated processing is idempotent.
10. Future-session information cannot leak into the current PatientContext.
11. A character's stable traits cannot change merely because one session ended.
12. Contradictory memories are preserved and surfaced for controlled resolution.
13. ACT process state is not treated as a personality measurement.
14. No clinical validity claim is implied by simulation parameters.

## 18. Implementation roadmap

### Phase A — Specification and domain contracts

- Publish this specification.
- Add immutable Python contracts for profile, dynamic state, event, and memory proposals.
- Define the AVA authoring profile without inventing unsupported traits.

### Phase B — Persistence

- Add a restricted-database personality profile migration.
- Add operational character-state migrations.
- Add immutable profile repositories.
- Add state snapshot and transition repositories.
- Add checksums and migration tests.

### Phase C — Context integration

- Extend PatientContext with the personality profile and dynamic state.
- Load the exact profile version for the run.
- Serialize only explicitly permitted fields.
- Add profile and state integrity checks.

### Phase D — Dynamics and memory services

- Implement event proposal validation.
- Implement memory proposal and evidence validation.
- Implement safe memory activation and supersession.
- Implement state-transition validation.
- Provide deterministic related/repeated/possible-contradiction suggestions
  and evidence-preserving, reviewer-approved consolidation proposals. The
  heuristic does not verify clinical meaning or resolve contradictions.

### Phase E — Patient Agent integration

- Update the prompt and context schema.
- Add controlled personality-conditioned response behavior.
- Add structured, versioned continuity proposals.
- Preserve the conversational content contract and idempotent interaction pipeline.

### Phase F — Longitudinal verification

- Test continuity across variable-length session sequences, including the three-session AVA-001 example.
- Test different trajectories from the same starting profile.
- Test memory retrieval and disclosure limits.
- Test state changes and personality stability.
- Test cross-run isolation.
- Test contradictions, retries, and failure recovery.

### Phase G — Authoring and user interface

- Add character profile authoring.
- Add profile review and version selection.
- Add run-specific memory and state inspection.
- Add a review interface for candidate memories and state proposals.

## 19. Acceptance criteria

The character-centered system is not complete merely because profile data can be stored.

A usable implementation must demonstrate that:

- A character behaves consistently with the authored profile.
- A character remembers relevant experiences from previous sessions.
- The same character can follow different trajectories in independent runs.
- Interactions can alter dynamic state without arbitrarily rewriting personality.
- Memory is source-linked and appropriately classified.
- New information can revise a character's beliefs while preserving historical provenance.
- The Patient Agent does not reveal restricted information prematurely.
- The complete process works through the real local model integration.

No claim of clinical efficacy, psychometric validity, or validated therapist competence follows from these engineering acceptance criteria.

## 20. Selected theoretical foundations

The following works inform the conceptual layers. They do not establish clinical validation of the TheraSim implementation.

- Conway, M. A., & Pleydell-Pearce, C. W. (2000). The construction of autobiographical memories in the self-memory system. *Psychological Review, 107*(2), 261–288.
- Gross, J. J. (1998). The emerging field of emotion regulation: An integrative review. *Review of General Psychology, 2*(3), 271–299.
- Hayes, S. C., Strosahl, K. D., & Wilson, K. G. (2012). *Acceptance and Commitment Therapy: The Process and Practice of Mindful Change* (2nd ed.).
- Mikulincer, M., & Shaver, P. R. (2016). *Attachment in Adulthood: Structure, Dynamics, and Change* (2nd ed.).
- Wiggins, J. S. (1991). Agency and communion as conceptual coordinates for the understanding and measurement of interpersonal behavior.
- Young, J. E., Klosko, J. S., & Weishaar, M. E. (2003). *Schema Therapy: A Practitioner's Guide*.
