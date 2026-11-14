# TheraSim

**A Local-First Framework for Psychotherapy Skills Simulation and Evidence-Grounded Evaluation**

TheraSim is a research-oriented project proposing a local-first, LLM-assisted environment for psychotherapy training, conversational simulation, and structured evaluation of therapist behavior.

**Project Status:** Research Prototype / Pre-MVP  
**Initial Therapeutic Framework:** Acceptance and Commitment Therapy (ACT)  
**Initial Simulation Scope:** One fictional client, three sequential sessions

**Copyright:** © 2026 Mohammad Mahdi Almasi Dargah. All rights reserved. See [COPYRIGHT.md](COPYRIGHT.md).

## Overview

TheraSim aims to provide a controlled environment in which users can practice psychotherapy-related conversational skills with a simulated client and receive structured, evidence-grounded feedback.

The initial design focuses on ACT and uses a fictional case to explore therapist behavior, client-state continuity, controlled disclosure, and longitudinal evaluation across multiple sessions.

The system is designed primarily for local execution, with an emphasis on data control, reproducibility, modular architecture, and explicit separation between simulated client information and evaluator-visible information.

## System Architecture

The proposed architecture contains two primary LLM agents:

- **Patient Agent:** Simulates a fictional client using a structured case specification, disclosure constraints, and longitudinal memory.
- **Evaluator Agent:** Assesses therapist behavior using versioned evaluation rubrics and finalized conversation transcripts.

Supporting components are internal application services rather than independent primary LLM agents:

- **Event Processing Service:** Extracts candidate interaction events.
- **Memory Service:** Manages validated longitudinal memory.
- **Clinical State Engine:** Maintains canonical simulation state and controls state transitions.
- **Orchestrator:** Coordinates session execution, service communication, and evaluation workflows.

The Evaluator Agent is isolated from hidden case formulations, undisclosed client information, and internal Patient Agent instructions.

## Evaluation Framework

TheraSim defines two distinct evaluation scopes:

**1. Session-Level Evaluation**

Assesses therapist behavior within a single completed session using a versioned ACT competency rubric.

Rubric: `ACT_RUBRIC_V0`  
Version: `0.2`

**2. Longitudinal Evaluation**

Assesses therapist behavior across a complete three-session simulation run, considering continuity, adaptation, therapeutic processes, and the handling of change over time.

Rubric: `ACT_LONGITUDINAL_RUBRIC_V0`  
Version: `0.1`

The two evaluation scopes remain separate. The framework does not assume that rubric scores are validated psychological measurements or automatically combine them into an overall competence score.

## Initial Research Scenario

The initial scenario, `AVA-001`, represents a fictional client participating in three sequential ACT-oriented psychotherapy sessions.

The scenario includes structured case facts, disclosure constraints, longitudinal continuity requirements, and rules for preserving the distinction between observable information and restricted case information.

## Proposed Technology Stack

The planned implementation uses:

- Python and FastAPI for the backend.
- Pydantic for typed data contracts.
- SQLite for local persistence.
- Ollama for local LLM execution.
- React for the user interface.
- Pytest for automated testing.

These technologies describe the intended implementation stack; the executable MVP has not yet been implemented.

## Repository Structure

```text
TheraSim/
├── docs/
│   ├── PROJECT_CHARTER.md
│   ├── CLINICAL_SIMULATION_SPEC.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── DATA_CONTRACTS.md
│   ├── STATE_TRANSITIONS.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_CONTRACTS.md
│   ├── SECURITY_BOUNDARIES.md
│   ├── AGENT_PROMPT_SPEC.md
│   ├── TEST_STRATEGY.md
│   └── MVP_DECISIONS.md
├── scenarios/
│   └── act/
│       └── CASE_001.md
└── rubrics/
    └── act/
        ├── ACT_RUBRIC_V0.md
        └── ACT_LONGITUDINAL_RUBRIC_V0.md
```

## Research and Safety Boundaries

TheraSim is intended for educational simulation and research into AI-supported psychotherapy skills training.

It is not designed to:

- Provide real-world psychotherapy.
- Diagnose mental health conditions.
- Replace qualified clinical supervision.
- Certify therapist competence.
- Serve as a validated psychometric instrument.

The evaluation rubrics are experimental and require independent human review and empirical validation.

The current repository documents a proposed architecture, data contracts, synthetic scenario, and evaluation framework. It does not yet contain a completed executable MVP or empirical evidence of training effectiveness.

## Current Development Status

The current stage establishes the architectural and research foundation for the initial MVP.

Future implementation work will focus on:

1. Backend and local persistence infrastructure.
2. Patient Agent integration.
3. Clinical State Engine and validated memory processing.
4. Session lifecycle and transcript management.
5. Evaluator Agent and versioned rubric execution.
6. Automated tests and human-reviewed benchmark datasets.
7. Local-first user interface.

## Research Position

TheraSim is an exploratory system-design project. Its contribution at this stage is the proposed architecture and evaluation specification for controlled, longitudinal psychotherapy skills simulation.

No claims of clinical efficacy, validated measurement, or professional certification are made.
