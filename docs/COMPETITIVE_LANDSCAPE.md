# TheraSim - Competitive Landscape

Last reviewed: 2026-11-14

## Purpose

This document records relevant research papers, existing products,
open-source implementations, and patent publications related to
AI-based psychotherapy simulation and therapist training.

This is a preliminary landscape review, not an exhaustive systematic
review or a legal freedom-to-operate opinion.

## 1. Relevant Research and Systems

### ClientBot (2019)

Development and Evaluation of ClientBot:
Patient-Like Conversational Agent to Train Basic Counseling Skills.

DOI: https://doi.org/10.2196/12529

Main contributions:
- Conversational simulated client.
- Training of open questions and reflections.
- Performance feedback during practice.
- Evaluation with 151 nontherapist participants.

Limitations relevant to TheraSim:
- Earlier neural conversational architecture.
- Limited long-term topic tracking.
- Focus on basic counseling skills rather than a complete multi-session
  modality-specific psychotherapy course.

### IMBUE (2024)

IMBUE: Improving Interpersonal Effectiveness through Simulation
and Just-in-Time Feedback with Human-Language Model Interaction.

URL: https://aclanthology.org/2024.acl-long.47/

Main contributions:
- DBT-informed interpersonal effectiveness training.
- DEAR MAN framework.
- Simulation and structured feedback.
- Randomized evaluation with 86 participants.

Implication:
A psychology-based simulation and feedback framework is not
sufficient by itself to establish novelty.

### CBT Trainer (2026)

An AI-Driven Virtual Patient Platform for Training Cognitive
Behavioral Therapy Practitioners Against Competencies.

DOI: https://doi.org/10.2196/84091

Main contributions:
- AI simulated patients.
- Competency-based feedback.
- CTS-R and UCL PWP assessment frameworks.
- Evaluation involving 59 active participants.
- Mean SUS score of 82.2.

Implication:
TheraSim must not claim that simulated CBT patients and
competency-based AI feedback are new ideas.

### ACT Interactive Patient Avatar (2026)

Toward Accessible Psychotherapy Training Using AI-Driven
Interactive Patient Avatars.

DOI: https://doi.org/10.1109/ICHI69079.2026.00124

Main contributions:
- ACT-oriented virtual patient.
- Spoken interaction.
- Separate evaluator.
- ACT fidelity criteria.
- Evaluation involving practicing psychologists and
  49 therapy transcripts.

Implication:
An ACT patient plus a separate ACT evaluator is already
represented in published research.

### Adaptive Virtual Patient (AVP, 2026)

Empirically Grounded Behavioral Adaptivity for LLM-Based
Virtual Patients in Psychotherapy Training.

URL: https://aclanthology.org/2026.findings-emnlp.1349/

Main contributions:
- Adaptive disclosure behavior.
- Therapist empathy and exploration influence patient openness.
- Separate behavioral dynamics module.
- Evaluation with 20 clinicians and trainees across
  80 sessions and 1,033 dialogue turns.

Implication:
Adaptive client behavior cannot be claimed as a general novelty.

### CARE: Classroom Integration (2026)

Classroom Integration of AI-Simulated Patients and Automated
Feedback in Doctoral Psychotherapy Training:
Longitudinal Mixed Methods Study.

DOI: https://doi.org/10.2196/93199

Publication date: 2026-11-11.

Main contributions:
- AI simulated patients in doctoral psychotherapy education.
- Automated feedback in educational settings.
- Longitudinal classroom deployment.

Relevant design observations:
- Learners identified a need for better progress tracking.
- Technical problems included transcription errors and
  simulated patient interruptions.
- Privacy and trust in automated feedback were important concerns.

### Virtual Standardized Patient Simulator

URL:
https://github.com/igembitsky/virtual-standardized-patient

Main contributions:
- Open-source offline patient simulation.
- Ollama integration.
- Qwen3 4B model.
- Clinician-authored case files.
- Local data storage.
- Automated consistency tests.

Implication:
Offline execution, Ollama integration, and open-source
patient simulation are not sufficient novelty claims.

## 2. Patent Landscape

### US20260204425A1

Title:
System and Method for Chat-Based Training Simulations for Mental
Health Professionals Using Large Language Models and Evidence-Based
Psychological Principles.

URL:
https://patents.google.com/patent/US20260204425A1/en

Application date: 2025-01-12.
Publication date: 2026-07-16.
Listed status: Pending.

Relevant concepts:
- Scenario prompting engine.
- LLM-generated virtual patient interactions.
- Transcript management.
- Analytical feedback engine.
- Performance reports.
- Dynamic scenario adaptation.

This is a highly relevant patent publication and must be
included in future novelty and IP review.

No legal freedom-to-operate conclusion has been made.

### WO2026112646A1

URL:
https://patents.google.com/patent/WO2026112646A1/en

Adjacent healthcare simulation patent publication:
- Virtual patient models.
- Dynamic state updates.
- Trainee action assessment.
- Performance feedback.

This is broader medical simulation prior art rather than
a specifically psychotherapy-focused implementation.

## 3. Preliminary Competitive Conclusions

The following concepts already have direct or adjacent precedents:

- AI virtual patients.
- Psychotherapy training simulations.
- LLM-generated patient dialogue.
- Separate patient and evaluator components.
- Modality-specific therapist feedback.
- Adaptive disclosure behavior.
- Offline local patient simulation.
- Multilingual virtual patient interfaces.

TheraSim must therefore differentiate itself through a clearly
specified combination of technical and educational properties.

## 4. Key Development Direction

The proposed differentiating research direction is:

Longitudinal Psychotherapy Simulation with Structured Clinical
State Management and Explainable Modality-Specific Assessment.

The main research hypothesis is that a structured and persistent
simulation engine can maintain coherent client state across
multiple sessions while separately evaluating therapist actions
against explicit modality-specific criteria.

This hypothesis requires experimental verification.

## 5. Review Limitations

- This is a preliminary search, not a systematic review.
- Patent claims have not been examined by a patent attorney.
- The absence of an identified feature in a paper does not prove
  that no other implementation has that feature.
- Product features and model licenses need independent verification.
