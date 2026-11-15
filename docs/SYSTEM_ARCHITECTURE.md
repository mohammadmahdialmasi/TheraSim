# TheraSim — System Architecture

**Document Version:** 0.1  
**Project Status:** Research Prototype / Pre-MVP  
**Last Updated:** 2026-11-14

---

## 1. Architecture Overview

TheraSim uses a modular, multi-agent architecture designed to simulate longitudinal psychotherapy training sessions.

The system separates conversational simulation, clinical state management, performance evaluation, and persistent storage into independent components.

The initial implementation focuses on Acceptance and Commitment Therapy (ACT), with an architecture that supports future integration of other therapeutic modalities.

### Core Components

1. Orchestrator
2. Patient Agent
3. Therapist Interface
4. Clinical State Engine
5. Evaluator Agent
6. Memory and Session Store
7. Model Provider Layer
8. Safety and Access Control Layer

---

## 2. Component Responsibilities

### 2.1 Orchestrator

The Orchestrator controls the execution flow of the simulation.

Responsibilities:

- Create and initialize simulation sessions.
- Load the appropriate synthetic case.
- Initialize the Patient Agent.
- Receive therapist messages.
- Coordinate state updates.
- Trigger session termination.
- Invoke the Evaluator Agent after session completion.
- Store session outputs and evaluation reports.

The Orchestrator must not independently generate clinical conclusions.

### 2.2 Patient Agent

The Patient Agent simulates a fictional client based on a predefined case.

Responsibilities:

- Maintain a consistent fictional identity.
- Generate contextually appropriate responses.
- Preserve relevant personal history across sessions.
- Respond according to the current disclosure level.
- Demonstrate avoidance, willingness, emotional reactions, and behavioral patterns.
- React naturally to therapist interventions.
- Avoid automatically rewarding technically correct interventions.

The Patient Agent must not reveal hidden case information without an appropriate conversational basis.

### 2.3 Therapist Interface

The Therapist Interface provides the environment in which the user conducts simulated sessions.

Responsibilities:

- Display the synthetic client conversation.
- Accept therapist messages.
- Display session history.
- Allow session termination.
- Present post-session evaluation reports.
- Display longitudinal changes across sessions.

### 2.4 Clinical State Engine

The Clinical State Engine manages structured changes in the simulated client's state.

Responsibilities:

- Maintain the current state of the synthetic client.
- Track changes across sessions.
- Validate state transitions.
- Record the evidence associated with state updates.
- Prevent unsupported or arbitrary changes.
- Preserve consistency between sessions.

Initial state variables include:

- Therapeutic alliance.
- Disclosure readiness.
- Experiential avoidance.
- Willingness.
- Values clarity.
- Committed action readiness.

All initial numerical values are simulation parameters, not validated psychological measurements.

The State Engine must use explicit transition rules and validated inputs rather than unrestricted language-model decisions.

### 2.5 Evaluator Agent

The Evaluator Agent assesses the therapist's performance using a versioned therapeutic rubric.

Responsibilities:

- Analyze the session transcript.
- Evaluate relevant therapeutic competencies.
- Identify strengths and areas for improvement.
- Provide evidence-linked feedback.
- Distinguish observed behavior from interpretation.
- Identify missing evidence.
- Produce structured evaluation reports.

The Evaluator Agent must not access hidden case information that was unavailable to the therapist.

Its evaluation must be based on:

1. The session transcript.
2. The applicable evaluation rubric.
3. Relevant session context legitimately available to the therapist.
4. Explicit evaluation instructions.

### 2.6 Memory and Session Store

This component manages persistent simulation data.

Responsibilities:

- Store synthetic case definitions.
- Store session transcripts.
- Store structured clinical states.
- Store longitudinal memory.
- Store evaluation reports.
- Preserve session sequence.
- Support reproducibility and session recovery.

The initial implementation will use SQLite.

### 2.7 Model Provider Layer

This component abstracts access to language models.

Initial requirements:

- Local model execution.
- Ollama integration.
- Configurable model selection.
- Independent model configuration for different agents.
- No mandatory external API.
- Support for future provider integrations.

### 2.8 Safety and Access Control Layer

This layer enforces boundaries between system components.

Responsibilities:

- Prevent unauthorized access to hidden case information.
- Separate simulation data from evaluation data.
- Prevent accidental disclosure of internal prompts.
- Maintain educational-use boundaries.
- Identify safety-critical statements requiring predefined handling.
- Prevent the system from presenting simulation results as clinical diagnosis or real treatment recommendations.

---

## 3. Data Access Boundaries

Each component must receive only the information required for its responsibilities.

| Component | Permitted Data |
|---|---|
| Patient Agent | Synthetic identity, clinical formulation, current state, relevant longitudinal memory |
| Therapist Interface | Information disclosed during the simulated interaction |
| Clinical State Engine | Current structured state, validated events, transition rules |
| Evaluator Agent | Transcript, rubric, legitimate session context |
| Orchestrator | Session metadata and component interfaces |
| Memory Store | Authorized structured records and session data |

### Information Isolation

The Evaluator Agent must not receive:

- Hidden case formulation.
- Undisclosed client history.
- Internal Patient Agent instructions.
- Future planned client responses.

This restriction is essential for preventing evaluation bias.

---

## 4. Simulation Lifecycle

The initial simulation lifecycle consists of the following stages:

1. Case selection.
2. Session initialization.
3. Patient Agent initialization.
4. Therapist-client interaction.
5. Structured event extraction.
6. Clinical state validation and update.
7. Session termination.
8. Evaluation generation.
9. Report storage.
10. Preparation for the next session.

Each stage must be independently traceable.

---

## 5. Initial Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python |
| API | FastAPI |
| Data Validation | Pydantic |
| Database | SQLite |
| Local Model Runtime | Ollama |
| Frontend | React |
| Version Control | Git |
| Testing | Pytest |

Technology choices are provisional and may be revised during implementation.

---

## 6. Architectural Principles

The system must follow these principles:

1. Modularity: Each component has a clearly defined responsibility.
2. Separation of Concerns: Simulation, evaluation, state management, and storage remain independent.
3. Reproducibility: Sessions must be traceable and versioned.
4. Explainability: Evaluations must reference observable conversational evidence.
5. Longitudinal Consistency: Client behavior must remain coherent across sessions.
6. Local-First: Core functionality must not require external APIs.
7. Persian-first MVP: Persian is required for the initial end-to-end workflow; English localization is deferred until the Persian workflow is stable.
8. Extensibility: Additional therapeutic modalities must be integrable without redesigning the entire system.
9. Clinical Boundaries: The platform is an educational simulation, not a clinical service.

---

## 7. Initial Implementation Scope

The first MVP will include:

- One synthetic ACT case.
- Three connected simulation sessions.
- One Patient Agent.
- One Evaluator Agent.
- One Clinical State Engine.
- Persistent session storage.
- Versioned ACT evaluation rubric.
- Persian-first interface.
- Local model execution through Ollama.

Features outside this scope will be considered for subsequent development.

---

## 8. Open Architectural Questions

The following decisions require further design:

- How should structured events be extracted from conversations?
- Which state transitions should be deterministic?
- Which decisions may involve language models?
- How should uncertainty be represented in evaluation reports?
- How should memory be summarized without losing clinically relevant information?
- How should multiple therapeutic modalities share the same infrastructure?
- How should model versions and generation parameters be recorded?
- How should reproducibility be evaluated across different local models?

These questions must be addressed before implementation.

---

**End of Document**