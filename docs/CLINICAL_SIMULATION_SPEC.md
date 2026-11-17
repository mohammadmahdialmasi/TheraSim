# TheraSim - Clinical Simulation Specification

Version: 0.1
Status: Draft
Modality: Acceptance and Commitment Therapy
Initial Case: AVA-001

## 1. Purpose

Define the clinical and behavioral architecture of the
simulated client environment.

The system is intended for educational psychotherapy
simulation, therapist skills practice, and research.

It is not a diagnostic or treatment system.

## 2. Clinical Foundation

The initial simulation is based on the ACT psychological
flexibility model.

The six interconnected processes are:

1. Acceptance
2. Cognitive Defusion
3. Present-Moment Awareness
4. Self-as-Context
5. Values
6. Committed Action

The processes are not a mandatory linear treatment sequence.

The clinical formulation must consider the function of
behavior in context rather than merely identifying symptoms.

Reference:
https://contextualscience.org/six_core_processes_act

ACT Case Formulation:
https://contextualscience.org/act_case_formulation_framework

## 3. Simulation Architecture

Every simulated client must have five distinct information layers.

### A. Stable Identity

Information that should remain consistent:

- Name
- Age
- Occupation
- Life history
- Relationships
- Personality characteristics
- Relevant background events

### B. Clinical Formulation

A provisional functional formulation:

- Presenting concerns
- Triggering situations
- Private experiences
- Avoidance patterns
- Immediate consequences
- Long-term consequences
- Values
- Resources
- Contextual factors
- Alternative behaviors

### C. Dynamic State

The internal simulation state may include:

- Therapeutic alliance
- Disclosure readiness
- Avoidance pattern strength
- Willingness to contact discomfort
- Values clarity
- Committed action readiness
- Treatment engagement

### D. Session State

Each session must preserve:

- Session number
- Session objectives
- Therapist interventions
- Patient responses
- Important disclosures
- Session events
- Agreed exercises
- Between-session events

### E. Longitudinal Memory

The system must remember:

- What occurred in previous sessions
- What the therapist promised or suggested
- What the client accepted or declined
- What happened between sessions
- Unresolved topics
- Changes in the functional formulation

## 4. State Representation

For the initial prototype, selected internal variables
may use an ordinal 0-4 simulation index.

These are engineering parameters, not validated
psychological tests, clinical scores, or measurements
of an actual person's mental state.

Initial AVA-001 state:

| Variable | Initial value | Direction |
|---|---:|---|
| Therapeutic alliance | 2 | Higher = stronger |
| Disclosure readiness | 1 | Higher = more open |
| Avoidance pattern strength | 4 | Higher = stronger |
| Willingness to contact discomfort | 1 | Higher = greater |
| Values clarity | 2 | Higher = clearer |
| Committed action readiness | 1 | Higher = greater |

No numerical state should be changed simply because
the therapist uses a supposedly correct technique.

Every update must be supported by:
- A relevant interaction
- Client response
- Contextual information
- An explicit state transition rule

Uncertain changes should remain unchanged or be marked
for review.

## 5. Patient Disclosure Architecture

The client must not reveal the entire case history
during the opening dialogue.

Information should be disclosed progressively.

Disclosure can depend on:

- Relevance of the therapist's question
- Perceived safety
- Conversational context
- Previous disclosures
- Therapeutic alliance
- Client readiness

The model must not reveal hidden case information
simply because the system prompt contains it.

## 6. Behavioral Adaptation

Patient behavior must remain consistent with the
functional formulation.

Possible responses include:

- Cooperation
- Hesitation
- Avoidance
- Uncertainty
- Partial engagement
- Resistance
- Reflection
- Increased disclosure

Therapeutic interventions must not produce
automatic positive reinforcement.

A technically appropriate intervention may fail,
be poorly timed, or receive a mixed response.

A patient may also improve in one domain while
remaining unchanged in another.

## 7. Session Continuity

Session N+1 must receive a structured summary of
session N and relevant state changes.

Important events must not disappear because
the conversation context becomes too long.

The system must distinguish:

- Confirmed case facts
- Client interpretations
- Therapist hypotheses
- Simulation state
- Unresolved questions

The AI must never convert a therapist hypothesis
into an established fact without supporting evidence.

## 8. Three-Session Training Scope

Session 1:
Relationship, contextual assessment, and functional analysis.

Session 2:
Review of between-session experience, defusion,
acceptance, and willingness.

Session 3:
Values clarification, committed action,
barrier analysis, and longitudinal review.

This is a three-session educational vignette,
not a complete psychotherapy protocol.

## 9. Safety

All initial cases are fictional.

The simulation must not replace a clinical
risk assessment by a human professional.

For AVA-001, no current acute safety crisis is
specified in the authored case.

Direct questions about safety must receive consistent
answers based on the case specification.

The system must not invent self-harm or suicide risk
simply to make a scenario more dramatic.

Any future high-risk scenarios require separately
designed safety protocols and expert review.

## 10. Evaluator Separation

Patient Agent and Evaluator Agent must operate
with separate instructions and access boundaries.

The Patient Agent generates client behavior.

The Evaluator Agent assesses therapist behavior.

The evaluator must not access hidden patient
information as evidence that the therapist
should have discovered it.

The evaluator should distinguish:
- Observed competence
- Unobserved competence
- Contradictory evidence
- Insufficient evidence

## 11. Ethical Boundaries

- No real-client identifying information.
- No autonomous clinical diagnosis.
- No treatment recommendations to real clients.
- No automated professional certification.
- Human expert oversight for clinical validation.
- Explicit synthetic-data labeling.

## 12. Development Status

This specification is an initial design document.

It must be reviewed by qualified ACT practitioners
before use in a clinical education study.

<!-- CHARACTER_CLINICAL_SIMULATION_NOTE_V0_1 -->
## Character definition versus therapeutic process

A synthetic client must have a stable character definition that is distinct
from the therapeutic goals and ACT process variables used in a scenario.

The character definition describes relatively stable tendencies, personal
history, communication characteristics, and authored hypotheses.

The therapeutic process describes what happens during the simulation:
interaction, disclosure, alliance, willingness, values exploration,
interventions, and reported outcomes.

The simulation must not assume that an ACT intervention changes personality.
It may influence the character's momentary state, interpretation, behavior,
or later learning when supported by the actual interaction history.

See `CHARACTER_MODEL_SPEC.md`.
