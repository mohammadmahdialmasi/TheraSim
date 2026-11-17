# TheraSim - Novelty Hypotheses

## 1. Core Research Direction

Longitudinal Psychotherapy Simulation with Structured Clinical
State Management and Explainable Therapist Competency Assessment.

## 2. Proposed Differentiating Components

### H1 - Longitudinal Clinical State Engine

Maintain a structured client state across a complete simulated
course of psychotherapy, including:

- Therapeutic alliance.
- Disclosure behavior.
- Treatment engagement.
- Relevant cognitive and behavioral processes.
- Session events.
- Between-session assignments.
- Unresolved therapeutic topics.
- Case formulation updates.

State changes must be traceable to defined rules and evidence
from the simulation, not arbitrary LLM-generated numerical changes.

### H2 - Modality-Aware Simulation

Separate the general patient simulation engine from
modality-specific behavior and assessment modules.

Initial modality:
ACT.

Future modules:
CBT, DBT, Schema Therapy and other evidence-based approaches.

Each module must define:
- Relevant therapeutic concepts.
- Scenario goals.
- Expected therapist competencies.
- Patient response patterns.
- Evaluation criteria.

### H3 - Evidence-Grounded Evaluation

Each evaluation should include:

- Identified therapist behavior.
- Relevant transcript evidence.
- Applicable assessment criterion.
- Explanation of the assessment.
- Suggested alternative response.
- Confidence or abstention where appropriate.

### H4 - Multilingual and Cultural Adaptation

Support Persian and English with clinically equivalent
scenario definitions and evaluation criteria.

Translation alone does not qualify as cultural adaptation.

### H5 - Reproducible Local Simulation Benchmark

Develop a benchmark for:

- Patient consistency.
- Session-to-session memory.
- Behavioral adaptivity.
- Scenario adherence.
- Evaluation agreement with human experts.
- Robustness across language models.

## 3. Initial Research Questions

RQ1:
Can a structured state engine maintain coherent simulated client
behavior across multiple psychotherapy sessions?

RQ2:
Can an independent evaluator assess therapist behavior against
explicit modality-specific competency criteria?

RQ3:
How closely does automated feedback agree with trained
human supervisors?

RQ4:
Can multilingual simulations preserve clinical meaning
and evaluation consistency across languages?

RQ5:
Can local-first execution maintain acceptable simulation
quality while protecting user data?

## 4. MVP Scope

- One fictional client.
- ACT as the initial modality.
- Sequential sessions with no universal fixed count; AVA-001 remains a three-session example scenario.
- Persian-first interaction.
- English localization prepared.
- Local LLM execution.
- Patient Agent.
- Evaluator Agent.
- Structured Clinical State Engine.
- Persistent session memory.
- Evidence-linked session reports.
- Longitudinal evaluation.

## 5. Non-Claims

TheraSim will not claim to be:

- The first AI simulated patient.
- The first ACT virtual patient.
- The first system with a separate evaluator.
- The first offline LLM patient simulator.
- A replacement for clinical supervision.

## 6. Research Status

All proposed differentiating components are research hypotheses.
Their technical novelty, empirical contribution and legal
patentability remain to be investigated.
