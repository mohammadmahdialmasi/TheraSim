# TheraSim — Test Strategy and Benchmark Specification

**Document Version:** 0.2
**Project Status:** Research Prototype / Pre-MVP
**Last Updated:** 2026-11-14

---

## 1. Purpose

This document defines the testing strategy, quality assurance procedures, evaluation metrics, benchmark methodology, and acceptance criteria for TheraSim.

The purpose is to establish a reproducible framework for evaluating the technical and behavioral performance of the platform.

The testing strategy covers:

1. Software functionality.
2. Multi-agent integration.
3. Synthetic patient behavioral consistency.
4. Longitudinal continuity across sessions.
5. Controlled disclosure of case information.
6. Evaluator accuracy and evidence grounding.
7. Event extraction performance.
8. Clinical state transition validation.
9. Security and information isolation.
10. Persian and English language performance.
11. Local model compatibility.
12. Reproducibility and performance.

The system must distinguish between technical correctness, behavioral plausibility, and clinical validity.

Passing software tests does not establish that an agent simulates psychotherapy accurately or evaluates therapeutic competence validly.

---

## 2. Testing Philosophy

TheraSim follows a layered testing strategy.

### 2.1 Core Principles

**Evidence-Based Testing**

Every important behavioral requirement must have an associated test case and an observable expected result.

**Reproducibility**

Test configurations, model versions, prompt versions, case versions, and expected outputs must be recorded.

**Separation of Quality Dimensions**

The quality of Patient Agent simulation must be evaluated separately from the quality of Evaluator Agent outputs.

**Longitudinal Evaluation**

The system must be assessed across connected sessions, not only through isolated conversations.

**Model Independence**

Tests must be reusable across different local models without assuming identical outputs.

**Human Oversight**

Psychological plausibility and therapeutic evaluation quality require review by qualified human reviewers.

**Failure Transparency**

Missing evidence, model uncertainty, and incomplete verification must be reported rather than hidden.

---

## 3. Testing Levels

The initial testing framework contains six levels.

### 3.1 Unit Testing

Purpose:

Verify individual functions and components independently.

Examples:

- Input validation.
- Output schema validation.
- Identifier generation.
- State variable range validation.
- Transition rule execution.
- Event deduplication.
- Memory classification.
- Transcript ordering.
- API response formatting.

Primary tool:

- Pytest.

Unit tests should not require a running language model unless explicitly designed as model integration tests.

### 3.2 Integration Testing

Purpose:

Verify communication and data consistency between system components.

Examples:

- Orchestrator to Patient Agent.
- Patient Agent to response validator.
- Event Extractor to State Engine.
- State Engine to database.
- Evaluator to Evaluation Service.
- Memory Service to session storage.
- FastAPI to SQLite.

Integration tests should use controlled model responses where possible.

### 3.3 System Testing

Purpose:

Verify complete user-facing workflows.

Examples:

- Create a simulation run.
- Start a session.
- Submit therapist messages.
- Receive patient responses.
- Complete the session.
- Generate an evaluation.
- Retrieve the report.
- Continue the simulation in the next session.

System tests must verify the complete lifecycle rather than individual endpoints alone.

### 3.4 Behavioral Testing

Purpose:

Evaluate whether language-model agents behave according to their intended roles.

Examples:

- Identity consistency.
- Natural disclosure.
- Emotional and behavioral plausibility.
- ACT modality adherence.
- Evidence-grounded evaluation.
- Event classification.
- Longitudinal consistency.

Behavioral testing must account for model variability.

### 3.5 Security Testing

Purpose:

Verify access restrictions and protection against adversarial inputs.

Examples:

- Restricted case information leakage.
- Prompt injection.
- Unauthorized repository access.
- Invalid agent tool requests.
- Malformed model outputs.
- Unauthorized state modifications.
- Sensitive logging.

Security tests must include both automated and targeted manual assessments.

### 3.6 Acceptance Testing

Purpose:

Determine whether the MVP satisfies its documented functional and quality requirements.

Acceptance decisions must be based on explicit test results.

Passing acceptance tests must not automatically be described as clinical validation.

---

## 4. Test Environment

The initial benchmark environment is designed for local execution.

### 4.1 Hardware Context

The development environment includes:

- Windows operating system.
- Local NVIDIA GPU.
- Local system RAM.
- Local Ollama model runtime.
- Python backend.
- SQLite storage.

Actual hardware specifications must be recorded in each benchmark run.

### 4.2 Software Configuration

Every test run should record:

- Operating system version.
- Python version.
- Project Git commit.
- Dependency versions.
- Ollama version.
- Model identifier.
- Model artifact version or digest, where available.
- Prompt versions.
- Schema versions.
- Case version.
- Rubric version.
- Generation parameters.

### 4.3 Environment Isolation

The test environment must use separate test databases.

Tests must not modify development data or production-like simulation records.

Synthetic test cases must not contain identifiable real-client information.

### 4.4 Model Configuration

For each model, record:

- model_identifier
- model_version
- quantization, where applicable
- context_length
- temperature
- top_p
- maximum_output_tokens
- random_seed, when supported
- timeout
- hardware configuration

Different models must be compared under documented configurations.

An unsupported model parameter must not be silently assumed to have been applied.

---

## 5. Test Categories and Ownership

The following table defines the primary testing responsibilities.

| Component | Main Test Categories |
|---|---|
| Therapist Interface | Functional, integration, usability |
| Orchestrator | Workflow, reliability, concurrency |
| Patient Agent | Behavioral, identity, disclosure |
| Evaluator Agent | Rubric adherence, evidence grounding |
| Event Extraction Agent | Precision, recall, evidence accuracy |
| Clinical State Engine | Deterministic rules, state integrity |
| Memory Service | Continuity, classification, retrieval |
| Database Layer | Integrity, transactions, recovery |
| API Layer | Contract, authorization, error handling |
| Model Provider | Compatibility, performance, failures |
| Security Layer | Isolation, injection resistance, leakage |

Each test must have an identifiable owner and an explicit expected result.

---

# PART I — PATIENT AGENT EVALUATION

## 6. Patient Agent Quality Dimensions

The Patient Agent must be evaluated across multiple behavioral dimensions.

### 6.1 Identity Consistency

Measures whether the agent maintains the same fictional identity throughout the simulation.

Test dimensions:

- Name consistency.
- Age consistency.
- Occupation consistency.
- Family history consistency.
- Important life-event consistency.
- Established personal preference consistency.

Failure examples:

- Changing the client's occupation.
- Contradicting an established personal event without explanation.
- Inventing a new family relationship.
- Forgetting previously disclosed information.

### 6.2 Case Formulation Consistency

Measures whether responses remain compatible with the synthetic client's predefined formulation.

Test dimensions:

- Trigger consistency.
- Avoidance pattern consistency.
- Emotional response consistency.
- Maintaining-factor consistency.
- Interpersonal pattern consistency.

The agent must not mechanically repeat the formulation in every response.

### 6.3 Behavioral Plausibility

Measures whether the agent responds like a plausible fictional client rather than a therapeutic instruction-following chatbot.

Test dimensions:

- Natural conversational language.
- Emotional response appropriateness.
- Realistic hesitation.
- Ambivalence.
- Resistance.
- Uncertainty.
- Context-sensitive cooperation.

### 6.4 Controlled Disclosure

Measures whether sensitive case information is disclosed appropriately.

Test dimensions:

- Initial information boundaries.
- Response to direct questions.
- Response to indirect questions.
- Disclosure during appropriate therapeutic exploration.
- Resistance or hesitation when contextually plausible.
- Preservation of previously disclosed facts.

The objective is not to maximize disclosure.

The objective is to reproduce the disclosure behavior defined by the synthetic scenario.

### 6.5 Intervention Responsiveness

Measures whether the agent responds to actual therapeutic interaction rather than rewarding technique names.

Test dimensions:

- Intervention relevance.
- Collaborative delivery.
- Patient understanding.
- Patient acceptance or rejection.
- Emotional response.
- Changes in willingness or engagement.

Using an ACT technique must not automatically produce a positive patient response.

### 6.6 Conversational Quality

Measures:

- Relevance to the latest therapist message.
- Naturalness.
- Appropriate response length.
- Language consistency.
- Avoidance of repetitive output.
- Appropriate use of everyday language.

---

## 7. Patient Agent Test Scenarios

The initial ACT benchmark must include controlled conversational scenarios.

### Scenario A — Initial Presentation

Objective:

Verify that the synthetic client introduces the presenting concern without revealing the complete hidden case formulation.

Expected behavior:

- Appropriate initial disclosure.
- Consistent fictional identity.
- Natural conversational language.
- No premature disclosure of restricted information.

### Scenario B — Direct Questioning

Objective:

Evaluate how the agent handles direct questions about sensitive experiences.

Expected behavior:

The agent may respond directly, partially, cautiously, or with uncertainty according to the case-specific disclosure policy.

It must not reveal every restricted detail simply because a question was asked.

### Scenario C — Nonjudgmental Exploration

Objective:

Test how the patient responds when the therapist demonstrates accurate listening and contextual understanding.

Expected behavior:

A plausible response that may include greater openness, emotional acknowledgment, or continued uncertainty.

Improvement must not be guaranteed.

### Scenario D — Premature Advice

Objective:

Test patient behavior when the therapist gives advice before sufficiently understanding the problem.

Expected behavior:

The patient may show discomfort, disagreement, confusion, or limited engagement.

The response must remain case-specific.

### Scenario E — ACT Defusion Exercise

Objective:

Evaluate the response to a cognitive defusion intervention.

Expected behavior:

The patient may participate, hesitate, misunderstand, decline, or describe a change in their relationship with a thought.

Participation alone must not establish successful defusion.

### Scenario F — Values Clarification

Objective:

Test the patient's ability to explore meaningful directions and personal values.

Expected behavior:

The patient may express uncertainty, conflict, clarification, or limited understanding.

The agent must not automatically generate sophisticated values statements.

### Scenario G — Follow-Up Session

Objective:

Test continuity after a previous session.

Expected behavior:

- Recognition of previously discussed information.
- Appropriate reference to agreed homework.
- Correct handling of reported outcomes.
- Consistent fictional history.
- No fabricated recollection of events that did not occur.

### Scenario H — Contradictory or Uncertain Disclosure

Objective:

Test whether the agent can express uncertainty or revise an earlier statement without arbitrarily rewriting established facts.

Expected behavior:

The agent must preserve the distinction between uncertainty, correction, and contradiction.

---

## 8. Patient Agent Evaluation Metrics

Initial quality dimensions:

| Metric | Description |
|---|---|
| Identity Consistency | Preservation of fictional identity |
| Case Consistency | Compatibility with predefined case formulation |
| Disclosure Policy Adherence | Compliance with disclosure boundaries |
| Conversational Relevance | Relevance to therapist input |
| Behavioral Plausibility | Human-reviewer assessment of realism |
| Intervention Responsiveness | Contextual response to therapeutic interventions |
| Longitudinal Continuity | Preservation of information across sessions |
| Schema Validity | Validity of structured model output |

### 8.1 Scoring Procedure

Behavioral dimensions may be assessed using a structured human-review rubric.

A proposed four-level rating scale:

- 0: Clear failure.
- 1: Significant inconsistency.
- 2: Acceptable with limitations.
- 3: Strong performance.

A separate NE category should be available when the test does not provide enough evidence to assess a dimension.

These scores are engineering evaluation tools and must not be presented as validated psychological measures.

### 8.2 Critical Failures

The following failures should be tracked independently:

- Contradiction of critical case facts.
- Unauthorized disclosure of restricted information.
- Disclosure of hidden prompts.
- Fabricated important personal history.
- Major session-to-session continuity failure.

A high average quality score must not conceal a critical security or consistency failure.

---

# PART II — LONGITUDINAL CONTINUITY

## 9. Longitudinal Patient-State Continuity Evaluation

This section evaluates continuity of the simulated client's identity, disclosures, memory, and canonical state across sessions. It primarily tests the Patient Agent, Memory Service, and State Engine.

This is distinct from the Evaluator Agent's longitudinal assessment of therapist performance across the three-session simulation run, which is defined in Section 10.7.

Longitudinal consistency is one of the central properties of TheraSim.

Testing must examine the system across multiple connected sessions.

An isolated response test is insufficient.

### 9.1 Continuity Dimensions

The benchmark must evaluate:

1. Stable personal identity.
2. Previously disclosed facts.
3. Historical emotional responses.
4. Previously discussed therapeutic topics.
5. Agreed homework.
6. Reported homework outcomes.
7. Unresolved topics.
8. Historical state snapshots.
9. Changes in willingness and avoidance.
10. Consistency of disclosure history.

### 9.2 Cross-Session Test Design

Each longitudinal test must contain:

- Initial synthetic case definition.
- Session 1 transcript.
- Session 1 memory snapshot.
- Session 1 final state.
- Session 2 transcript.
- Session 2 memory snapshot.
- Session 2 final state.
- Session 3 transcript.
- Session 3 memory snapshot.
- Cross-session evaluation.

### 9.3 Continuity Failure Categories

Failures should be classified as:

- Fact loss.
- Fact contradiction.
- False memory.
- Incorrect homework recollection.
- Incorrect disclosure status.
- Unsupported state progression.
- Missing historical context.
- Inconsistent behavioral pattern.

### 9.4 Nonlinear Change Testing

The benchmark must explicitly include cases where the fictional client:

- Shows initial progress and later avoidance.
- Participates but reports no meaningful benefit.
- Agrees to homework but does not complete it.
- Reports partial success with continued discomfort.
- Changes an earlier interpretation.
- Maintains uncertainty across multiple sessions.

The system must not enforce an artificial improvement trajectory.

---

# PART III — EVALUATOR AGENT EVALUATION

## 10. Evaluator Quality Dimensions

The Evaluator Agent must be assessed independently of Patient Agent quality.

### 10.1 Rubric Adherence

Measures whether the evaluator:

- Uses the correct rubric version.
- Applies permitted rating values.
- Follows competency definitions.
- Respects the modality.
- Uses NE when evidence is insufficient.
- Avoids unauthorized aggregate scoring.

### 10.2 Evidence Grounding

Measures whether evaluation claims are supported by transcript evidence.

Test dimensions:

- Valid message references.
- Correct interpretation of therapist statements.
- Accurate evidence summaries.
- Relevance of supporting excerpts.
- Absence of fabricated evidence.

### 10.3 Rating Accuracy

Measures agreement between AI-generated ratings and qualified human reviewers using the same rubric.

The human reference ratings must be independently assigned before reconciliation.

### 10.4 Construct Relevance

Measures whether the evaluator assesses the intended therapeutic competency rather than superficial indicators.

For example:

Using the term cognitive defusion must not automatically receive a high defusion rating.

The evaluator should assess what the therapist actually did.

### 10.5 Uncertainty Calibration

Measures whether the evaluator correctly identifies cases in which the transcript provides insufficient information.

### 10.6 Feedback Quality

Measures whether the report provides:

- Specific observations.
- Actionable improvement suggestions.
- Accurate evidence references.
- Clear distinction between strengths and limitations.
- Appropriate acknowledgment of uncertainty.

---

### 10.7 Evaluation Scope and Rubric Routing

The Evaluator Agent supports two distinct evaluation scopes. The selected scope determines the rubric, eligible transcript evidence, required identifiers, and output validation rules.

**Session-level evaluation**

- Evaluates therapist behavior within one completed session only.
- Uses ACT_RUBRIC_V0, version 0.2.
- Must not infer therapist competence from events outside the supplied session transcript.
- Must identify the session and the exact rubric ID and version.

**Longitudinal run-level evaluation**

- Evaluates therapist behavior across the complete three-session simulation run.
- Uses ACT_LONGITUDINAL_RUBRIC_V0, version 0.1.
- Must not be generated until all three required sessions are complete and their final transcripts are available.
- Must consider the chronological relationship among sessions and may cite evidence from one or more session transcripts.
- Must identify the run, set session_id to null, and reference all three session transcripts as required by the rubric output contract.

**Shared controls**

- The Evaluator Agent receives only permitted final transcript(s), the selected versioned rubric, and therapist-visible context.
- It must not receive hidden case formulation, undisclosed case facts, Patient Agent prompts, or future disclosure plans.
- The evaluator must not substitute one rubric for the other, combine their dimension scores, or produce an undocumented overall score.
- Evaluation and human-reference datasets must preserve evaluation_scope, rubric ID, and rubric version. Session and longitudinal results must be analyzed separately.
- Each output must pass schema validation and evidence-reference validation before storage or display.
## 11. Human Reference Evaluation

Human expert evaluation is necessary for assessing the quality of the Evaluator Agent.

### 11.1 Reviewer Qualifications

Reviewers should have relevant expertise in clinical psychology, psychotherapy, or the specific therapeutic modality being evaluated.

ACT-specific ratings should ideally be completed by reviewers with demonstrated ACT training or relevant professional experience.

Reviewer qualifications must be documented.

### 11.2 Independent Rating

Each benchmark transcript should be evaluated independently by at least two qualified reviewers during the initial validation phase.

Reviewers should:

- Use the same rubric version.
- Receive the same authorized transcript.
- Remain blind to the AI-generated rating.
- Provide evidence references.
- Identify insufficient evidence.
- Record uncertainty.

### 11.3 Disagreement Resolution

Disagreements should be documented.

A third reviewer or structured adjudication procedure may be used to establish a reference label when necessary.

The original independent ratings must remain preserved.

Adjudicated ratings must not replace the original data in inter-rater reliability calculations.

### 11.4 Human Agreement Metrics

Depending on the rating structure:

- Weighted Cohen's kappa may be used for two reviewers assigning ordinal ratings.
- Krippendorff's alpha may be considered for multiple reviewers or incomplete rating data.
- Exact agreement and adjacent agreement should also be reported.
- Confidence intervals should accompany important reliability estimates when the sample size permits.

A single reliability statistic should not be interpreted without considering sample size, category prevalence, and rating distribution.

---

## 12. Evaluator Metrics

| Metric | Purpose |
|---|---|
| Exact Rating Agreement | Percentage of exact rating matches |
| Adjacent Rating Agreement | Percentage of ratings differing by at most one level |
| Weighted Kappa | Agreement adjusted for chance and ordinal disagreement |
| Krippendorff's Alpha | Reliability across multiple raters and incomplete data |
| Evidence Reference Validity | Percentage of references pointing to valid messages |
| Evidence Support Rate | Percentage of claims supported by cited content |
| Unsupported Claim Rate | Frequency of claims lacking evidence |
| NE Agreement | Agreement when evidence is insufficient |
| Feedback Actionability | Human-reviewer assessment of usefulness |

### 12.1 Important Distinction

Agreement with human reviewers does not automatically establish that the rubric itself is valid.

The validity of the underlying competency definitions requires separate theoretical and empirical examination.

---

# PART IV — EVENT EXTRACTION

## 13. Event Extraction Benchmark

The Event Extraction Agent converts conversation segments into candidate structured events.

Its outputs must be compared against human-annotated reference data.

### 13.1 Annotation Categories

The initial benchmark should include:

- Explicit disclosure.
- Emotional experience disclosure.
- Avoidance-related statements.
- Willingness expressions.
- Cognitive fusion indicators.
- Defusion-related responses.
- Present-moment awareness.
- Values clarification.
- Committed action reports.
- Homework agreement.
- Homework completion.
- Intervention acceptance.
- Intervention refusal.
- Ambiguous or insufficient evidence.

The final taxonomy must match the event schema implemented by the application.

### 13.2 Annotation Procedure

Each annotated example should contain:

- Transcript segment.
- Event type.
- Actor.
- Evidence message identifier.
- Evidence span.
- Observation classification.
- Confidence or uncertainty annotation.
- Adjudication status.

The annotation guidelines must distinguish direct statements from inferred psychological processes.

### 13.3 Reference Data

A human-annotated dataset should be developed using the synthetic ACT scenario.

Reviewers should independently annotate an appropriate subset of the dataset.

Disagreements should be documented and resolved through adjudication.

### 13.4 Metrics

Use:

- Precision.
- Recall.
- F1-score.
- Per-class F1.
- Evidence span overlap.
- Actor classification accuracy.
- False-positive rate.
- False-negative rate.

For event matching, the benchmark must define how a predicted event is matched to a reference event.

A match should require compatible event type, actor, and source evidence according to explicit annotation rules.

### 13.5 Conservative Extraction

The system should prioritize reliable evidence.

An ambiguous psychological interpretation should be marked as uncertain rather than automatically converted into a confirmed event.

---

# PART V — CLINICAL STATE ENGINE

## 14. State Transition Testing

The State Engine must be tested separately from model-generated event extraction.

Its deterministic rules should be verifiable through controlled test fixtures.

### 14.1 Functional Tests

Verify that:

- Values remain within the permitted range.
- Invalid variable names are rejected.
- Missing evidence is rejected or flagged.
- Incorrect message identifiers are rejected.
- Duplicate events do not create repeated transitions.
- Historical snapshots remain available.
- Rejected transitions do not modify canonical state.
- Accepted transitions create valid snapshots.

### 14.2 Behavioral Rule Tests

The benchmark must include:

**Test A — Intervention Without Patient Response**

Expected result:

No automatic positive state transition.

**Test B — Patient Participation Without Reported Benefit**

Expected result:

Participation does not automatically increase willingness or another state variable.

**Test C — Explicit Patient Refusal**

Expected result:

The system does not record a positive response simply because an intervention was offered.

**Test D — Contradictory Evidence**

Expected result:

Contradictory information is preserved and ambiguous transitions may require review.

**Test E — Nonlinear Progress**

Expected result:

A previous positive transition does not prevent a later negative or neutral transition.

**Test F — Duplicate Evidence**

Expected result:

The same event must not be applied twice.

### 14.3 State Engine Metrics

- Rule validation accuracy.
- Invalid transition rejection rate.
- Duplicate transition prevention rate.
- Historical reconstruction correctness.
- Evidence reference validity.
- State snapshot consistency.

For purely deterministic rules, the expected behavior should be verified through exact automated assertions rather than statistical model metrics.

---

# PART VI — MEMORY EVALUATION

## 15. Longitudinal Memory Benchmark

The Memory Service must be evaluated for information preservation and classification accuracy.

### 15.1 Memory Categories

The benchmark should distinguish:

- Explicitly disclosed facts.
- Therapist hypotheses.
- System-generated summaries.
- Reported homework outcomes.
- Structured interaction observations.
- Accepted state transitions.

### 15.2 Memory Quality Dimensions

**Recall**

Can the system retrieve relevant previously established information?

**Precision**

Does it retrieve relevant memory rather than unrelated historical content?

**Classification Accuracy**

Does it preserve the original information category?

**Source Traceability**

Can a memory item be linked to its supporting transcript messages?

**Contradiction Handling**

Does it preserve contradictory or revised information without silently overwriting history?

**False Memory Prevention**

Does it avoid generating events that were never part of the interaction?

### 15.3 Test Scenarios

- Retrieval of previously disclosed personal information.
- Retrieval of agreed homework.
- Retrieval of reported homework outcomes.
- Separation of therapist hypothesis from patient disclosure.
- Handling of corrected personal information.
- Handling of contradictory disclosures.
- Retrieval of an unresolved topic from an earlier session.
- Detection of irrelevant or outdated memory.

### 15.4 Memory Metrics

Potential metrics:

- Memory retrieval precision.
- Memory retrieval recall.
- Classification accuracy.
- Source reference validity.
- Contradiction preservation rate.
- False memory rate.
- Historical reconstruction accuracy.

Memory quality must not be assessed only by linguistic similarity between summaries.

Correct classification and source traceability are essential.

---

# PART VII — SECURITY BENCHMARK

## 16. Security Testing

The security benchmark must test whether critical information boundaries remain enforced.

### 16.1 Hidden Information Leakage

Test attempts to retrieve:

- Hidden clinical formulation.
- Undisclosed personal history.
- Patient Agent prompts.
- Internal simulation instructions.
- Evaluator internal instructions.

Tests should be performed through:

- Therapist messages.
- Direct API requests.
- Transcript injection.
- Memory injection.
- Malformed component requests.

Expected result:

Unauthorized restricted information is not disclosed.

### 16.2 Prompt Injection

Test adversarial inputs that attempt to:

- Override agent instructions.
- Reveal hidden case context.
- Modify evaluation ratings.
- Access internal tools.
- Execute arbitrary commands.
- Request database contents.
- Change state variables without validation.

### 16.3 Information Flow Validation

Verify that:

- Evaluator input excludes restricted case data.
- Frontend responses exclude internal state.
- Patient Agent cannot access unrelated cases.
- Agent tool permissions follow explicit allowlists.
- Internal logs do not expose secrets.
- Database files are not publicly served.

### 16.4 Security Metrics

| Metric | Description |
|---|---|
| Restricted Data Leakage | Number of unauthorized disclosures |
| Prompt Injection Success Rate | Successful adversarial instruction overrides |
| Unauthorized Tool Invocation | Attempts that bypass tool restrictions |
| Access Control Failure Rate | Unauthorized operations incorrectly accepted |
| Output Validation Failure Handling | Invalid outputs rejected correctly |

Critical information leakage is a release-blocking failure.

An average security score must never be used to excuse a single confirmed critical disclosure.

---

# PART VIII — MULTILINGUAL EVALUATION

## 17. Persian and English Performance

TheraSim is intended to support Persian and English.

The benchmark must evaluate both languages independently.

### 17.1 Persian Evaluation

Test dimensions:

- Conversational naturalness.
- Psychological vocabulary accuracy.
- Correct interpretation of colloquial language.
- Contextual understanding.
- Appropriate emotional expressions.
- Preservation of meaning in summarized memory.
- Accurate event extraction.
- Rubric adherence.
- Appropriate Persian response length and style.

### 17.2 English Evaluation

Use equivalent scenarios and behavioral requirements.

### 17.3 Cross-Language Consistency

The benchmark should assess whether the same case produces comparable behavioral patterns across languages.

The system must not assume that literal translation guarantees equivalent psychological meaning.

### 17.4 Language Comparison

Report Persian and English performance separately.

Where direct comparison is useful, use matched cases, equivalent prompts, and comparable test conditions.

A lower score in one language must not be hidden by averaging results across languages.

---

# PART IX — MODEL COMPARISON

## 18. Local Model Benchmark

One objective of TheraSim is to support multiple local language models.

Models should be compared across identical benchmark tasks.

### 18.1 Comparison Dimensions

- Patient behavioral quality.
- Identity consistency.
- Disclosure control.
- Longitudinal continuity.
- Evaluator rubric adherence.
- Evidence grounding.
- Event extraction performance.
- Structured output validity.
- Persian language quality.
- Generation latency.
- Memory consumption.
- GPU memory usage.
- Runtime failures.

### 18.2 Experimental Controls

For meaningful comparison:

1. Use the same case version.
2. Use the same test scenarios.
3. Use the same transcript inputs where applicable.
4. Use the same rubric version.
5. Record prompt versions.
6. Document generation parameters.
7. Record model quantization.
8. Repeat stochastic tests.
9. Keep hardware conditions as consistent as possible.
10. Document all deviations.

A model comparison is invalid when relevant experimental conditions are undocumented.

### 18.3 Repeated Runs

For stochastic model behavior, multiple runs should be performed.

The number of repetitions must be selected according to available computational resources and the variability being investigated.

Results must include the number of runs and, where appropriate, variability estimates and confidence intervals.

A single favorable model response is insufficient evidence of reliable performance.

### 18.4 Model Comparison Report

Each model report should include:

- Model identifier.
- Version or artifact digest.
- Quantization.
- Hardware configuration.
- Prompt versions.
- Benchmark version.
- Number of runs.
- Metric results.
- Failure examples.
- Limitations.

---

# PART X — BENCHMARK DATASET DESIGN

## 19. Dataset Structure

The initial benchmark dataset should contain structured test cases.

Each benchmark record should include:

- benchmark_case_id
- synthetic_case_id
- case_version
- modality
- language
- session_number
- scenario_type
- input_transcript
- expected_behavior
- expected_event_labels
- expected_evidence_references
- expected_state_constraints
- security_test_category
- annotation_status
- dataset_version

### 19.1 Dataset Categories

The initial dataset should include:

1. Patient simulation cases.
2. Longitudinal continuity cases.
3. Evaluator assessment transcripts.
4. Event extraction examples.
5. State transition fixtures.
6. Memory retrieval cases.
7. Prompt injection cases.
8. Persian language cases.
9. English language cases.
10. Failure recovery cases.

### 19.2 Dataset Separation

The dataset must be divided into:

- Development set.
- Validation set.
- Held-out test set.

Where cases are sufficiently numerous, splitting should occur at the case or scenario level rather than randomly splitting messages from the same conversation.

This reduces information leakage between training or prompt-development examples and held-out evaluation.

### 19.3 Version Control

Each benchmark dataset release must have:

- Dataset version.
- Changelog.
- Annotation guidelines.
- Case version references.
- Inclusion criteria.
- Known limitations.
- Integrity hash, where practical.

Historical benchmark versions must remain available for comparison.

### 19.4 Synthetic Data Limitations

A benchmark based on one synthetic client cannot establish generalizability across different populations or clinical presentations.

The initial case is suitable for MVP workflow testing, not for claiming broad clinical validity.

Additional synthetic cases and expert-reviewed scenarios will be required for stronger behavioral evaluation.

---

## 20. Benchmark Annotation Protocol

Human annotation must follow explicit guidelines.

### 20.1 Annotation Instructions

Reviewers must receive:

- The relevant benchmark transcript.
- Defined event categories or rating criteria.
- Operational definitions.
- Examples of positive and negative cases.
- Instructions for ambiguous evidence.
- Instructions for using NE where appropriate.

### 20.2 Independent Annotation

A selected portion of the dataset should be annotated independently by multiple reviewers.

The annotation process should record:

- Original independent labels.
- Disagreements.
- Adjudication decisions.
- Reviewer metadata.
- Annotation guideline version.

### 20.3 Annotation Quality

The project should estimate agreement for relevant annotation tasks.

For categorical event labels, suitable agreement statistics should be selected based on the annotation design.

For span annotations, overlap-based measures may be reported alongside exact agreement.

The choice of statistic must be documented rather than selected after observing favorable results.

### 20.4 Expert Review

ACT-specific scenarios and evaluator rubric labels should be reviewed by qualified experts.

Where possible, expert reviewers should be blinded to model identity during comparative assessment.

---

# PART XI — PERFORMANCE AND RELIABILITY

## 21. Performance Testing

The local-first architecture makes computational efficiency important.

### 21.1 Performance Metrics

Measure:

- Patient response latency.
- Evaluator generation latency.
- Event extraction latency.
- Total session interaction latency.
- Model initialization time.
- Memory consumption.
- GPU memory consumption.
- Database query latency.
- Database write latency.
- Failure rate.

### 21.2 Latency Measurement

Record:

- Request start time.
- Model invocation start time.
- First-token time, when streaming is supported.
- Generation completion time.
- Validation completion time.
- Database persistence completion time.

Median and high-percentile latency should be reported when enough observations are available.

### 21.3 Resource Monitoring

Record:

- CPU utilization.
- RAM utilization.
- GPU utilization.
- GPU memory usage.
- Model memory footprint.
- Disk usage.

### 21.4 Reliability Scenarios

Test:

- Model unavailable.
- Model timeout.
- Invalid model output.
- Interrupted session.
- Database write failure.
- Repeated API request.
- Application restart during an active simulation.
- Evaluation generation failure.

The system must preserve already committed records and avoid partially accepted state changes.

---

# PART XII — REPRODUCIBILITY

## 22. Reproducible Benchmark Execution

Every benchmark execution must produce a structured run manifest.

Required fields:

- benchmark_run_id
- benchmark_version
- dataset_version
- project_git_commit
- test_environment
- model_identifier
- model_version
- model_artifact_digest
- prompt_versions
- schema_versions
- case_version
- rubric_version
- generation_parameters
- execution_timestamp
- number_of_repetitions
- result_status

### 22.1 Repeatability

Deterministic tests should produce the same result under the same configuration.

Model-assisted tests may produce variable outputs.

Their variation must be measured and documented rather than treated as an automatic software failure.

### 22.2 Historical Comparison

Benchmark reports should support comparison across:

- Model versions.
- Prompt versions.
- Case versions.
- Application versions.
- Transition rule versions.
- Rubric versions.

Historical test results must not be overwritten when newer results are generated.

---

# PART XIII — ACCEPTANCE CRITERIA

## 23. MVP Acceptance Gates

The initial MVP requires separate acceptance gates.

### Gate 1 — Functional Reliability

Required:

- All mandatory API contract tests pass.
- Session lifecycle behaves correctly.
- Messages are persisted consistently.
- Database relationships remain valid.
- Failed operations do not corrupt completed records.

### Gate 2 — Agent Contract Compliance

Required:

- Patient Agent outputs satisfy the required schema.
- Evaluator outputs satisfy the required schema.
- Event extraction outputs satisfy the required schema.
- Invalid outputs are rejected or flagged.
- Agent failures do not bypass validation.

### Gate 3 — Information Isolation

Required:

- No confirmed restricted case disclosure to unauthorized components.
- Evaluator receives no hidden case formulation.
- Frontend responses exclude internal state and prompts.
- Agents cannot perform unauthorized system operations.

Any confirmed critical information leak blocks release.

### Gate 4 — State Integrity

Required:

- State values remain in defined ranges.
- Invalid transitions are rejected.
- Duplicate transitions are prevented.
- Historical snapshots remain recoverable.
- Accepted changes have traceable supporting evidence.

### Gate 5 — Behavioral Quality

Required:

- Patient identity consistency is evaluated across all initial sessions.
- Disclosure behavior is tested in multiple contexts.
- Nonlinear responses are included.
- ACT modality adherence is reviewed.
- Major behavioral failures are documented.

Quantitative quality thresholds must be established using pilot data and human review rather than invented in advance.

### Gate 6 — Evaluation Quality

Required:

- Evaluation ratings follow the correct rubric.
- Evidence references resolve to valid transcript content.
- Unsupported claims are tracked.
- NE is used when evidence is insufficient.
- Human comparison results are available for the pilot benchmark.

- Session-level therapist evaluations use ACT_RUBRIC_V0 and identify the correct session and rubric version.
- Run-level therapist evaluation is executed only after all three sessions are complete and uses ACT_LONGITUDINAL_RUBRIC_V0.
- Evaluation scope, rubric ID and version, run/session identifiers, and transcript references satisfy the applicable output contract.
- Session-level and longitudinal results remain separate; no unsupported aggregate score is produced.

### Gate 7 — Multilingual Functionality

Required:

- Persian and English interactions are supported.
- Critical schema and workflow tests pass in both languages.
- Persian-specific behavioral limitations are documented.

### Gate 8 — Reproducibility

Required:

- Model and prompt versions are recorded.
- Benchmark configurations are stored.
- Historical test results remain accessible.
- Benchmark runs can be compared.

---

## 24. Proposed Quality Threshold Policy

The project must avoid arbitrary numerical targets that lack empirical justification.

A threshold should be defined only after:

1. Establishing a baseline.
2. Reviewing representative pilot results.
3. Defining the cost of false positives and false negatives.
4. Consulting relevant domain experts.
5. Estimating measurement uncertainty.
6. Considering test-set size.
7. Confirming that the metric reflects the intended quality dimension.

### 24.1 Mandatory Hard Gates

Certain outcomes require strict engineering acceptance criteria.

Examples:

- Unauthorized restricted-data access: zero accepted cases in the defined security test suite.
- Invalid state values: zero accepted invalid values.
- Invalid foreign-key references: zero accepted invalid references.
- Duplicate idempotent operations: zero duplicate effects in the defined tests.
- Unauthorized state mutation by agents: zero accepted cases.

These requirements describe expected software behavior, not empirical claims about complete security.

### 24.2 Empirical Quality Thresholds

Thresholds for behavioral plausibility, evaluator agreement, and event extraction must be established through pilot evaluation.

The initial version should report baseline measurements without claiming that they establish clinical validity.

---

# PART XIV — REPORTING

## 25. Benchmark Report Structure

Each completed benchmark report should contain:

### 25.1 Executive Summary

- Benchmark objective.
- Benchmark version.
- Tested model.
- Project version.
- Main findings.
- Critical failures.

### 25.2 Environment

- Hardware.
- Operating system.
- Model runtime.
- Software versions.
- Generation settings.

### 25.3 Dataset

- Dataset version.
- Number of cases.
- Number of sessions.
- Number of transcripts.
- Number of annotated events.
- Language distribution.
- Annotation methodology.

### 25.4 Quantitative Results

Report the relevant metrics with:

- Metric definition.
- Number of observations.
- Result.
- Confidence interval, when appropriate.
- Relevant limitations.

### 25.5 Qualitative Analysis

Include representative examples of:

- Successful behavior.
- Behavioral inconsistency.
- Disclosure errors.
- Incorrect evaluations.
- Event extraction failures.
- Memory failures.
- Security failures.

Examples must use synthetic data and must not reveal restricted internal information unnecessarily.

### 25.6 Limitations

Every report must state:

- Sample size limitations.
- Model variability.
- Reviewer limitations.
- Dataset limitations.
- Unmeasured quality dimensions.
- Generalizability limitations.

### 25.7 Recommendations

Conclude with prioritized engineering improvements based on observed failures.

---

# PART XV — IMPLEMENTATION PLAN

## 26. Testing Implementation Phases

### Phase 1 — Testing Infrastructure

Implement:

- Pytest configuration.
- Test directory structure.
- Test fixtures.
- Test database setup.
- Mock model provider.
- Structured test result reporting.

### Phase 2 — Core Software Tests

Implement:

- Data schema tests.
- Repository tests.
- State transition tests.
- API contract tests.
- Session lifecycle tests.
- Error handling tests.

### Phase 3 — Agent Contract Tests

Implement:

- Patient response validation.
- Evaluator report validation.
- Event extraction validation.
- Prompt version tests.
- Model provider integration tests.

### Phase 4 — Behavioral Evaluation

Implement:

- Patient identity consistency scenarios.
- Disclosure control scenarios.
- ACT interaction scenarios.
- Longitudinal continuity scenarios.
- Human review procedures.

- Session-level ACT evaluator tests against ACT_RUBRIC_V0.
- Three-session longitudinal evaluator tests against ACT_LONGITUDINAL_RUBRIC_V0, including incomplete-run rejection.
- Human-reference evaluation is performed separately for each evaluation scope.

### Phase 5 — Benchmark Dataset

Develop:

- Versioned synthetic scenarios.
- Annotated transcripts.
- Event extraction reference labels.
- Evaluator reference ratings.
- Persian and English test pairs.
- Prompt injection cases.

### Phase 6 — Model Comparison

Run comparative experiments across selected local models.

Record:

- Behavioral performance.
- Evaluation agreement.
- Event extraction metrics.
- Latency.
- RAM and GPU consumption.
- Failure rates.

### Phase 7 — Regression and Release Testing

Before each release:

- Run unit tests.
- Run integration tests.
- Run API tests.
- Run security regression tests.
- Run critical behavioral tests.
- Compare benchmark results with previous versions.
- Document known limitations.

---

## 27. Initial Test Directory Structure

The proposed repository structure is:

```text
tests/
├── unit/
│   ├── test_schemas.py
│   ├── test_state_engine.py
│   ├── test_event_validation.py
│   ├── test_memory.py
│   └── test_repositories.py
│
├── integration/
│   ├── test_patient_pipeline.py
│   ├── test_evaluator_pipeline.py
│   ├── test_event_pipeline.py
│   └── test_session_lifecycle.py
│
├── api/
│   ├── test_cases_api.py
│   ├── test_sessions_api.py
│   ├── test_messages_api.py
│   └── test_evaluations_api.py
│
├── behavioral/
│   ├── patient/
│   ├── evaluator/
│   └── longitudinal/
│
├── security/
│   ├── test_information_leakage.py
│   ├── test_prompt_injection.py
│   └── test_access_control.py
│
├── benchmark/
│   ├── datasets/
│   ├── annotations/
│   ├── manifests/
│   └── reports/
│
└── fixtures/
    ├── cases/
    ├── transcripts/
    ├── events/
    └── evaluations/
```

This is a proposed future structure.

The directories should be created when the testing implementation begins, not necessarily during the documentation-only phase.

---

## 28. Open Research Questions

The following research questions should guide future benchmark development:

1. How accurately can local LLMs maintain synthetic client identity across multiple sessions?
2. How does model size affect controlled disclosure and behavioral plausibility?
3. Can structured state transitions reduce artificial or unsupported therapeutic progress?
4. How closely do AI-generated ACT evaluations agree with qualified human reviewers?
5. Does evidence-linked evaluation improve the reliability of automated feedback?
6. How does Persian-language performance differ from English-language performance?
7. How much longitudinal context is required to maintain continuity?
8. How do prompt version changes affect patient behavior and evaluator ratings?
9. Can smaller local models achieve acceptable performance without excessive memory consumption?
10. How robust are the agents against prompt injection embedded in simulated conversations?

These questions may support future empirical publications.

They must not be presented as established findings before data collection.

---

## 29. Important Validity Limitations

The initial MVP is a research prototype, not a validated psychotherapy training instrument.

Important limitations include:

- One initial synthetic case.
- A limited number of sessions.
- Model-dependent behavioral variability.
- Limited human annotation data.
- Possible cultural and linguistic biases.
- Unvalidated simulation state variables.
- Potential disagreement between human experts.
- Limited evidence of real-world training effectiveness.

The project must distinguish:

**Software Validation:** Does the software behave according to its technical specification?

**Behavioral Validation:** Does the synthetic client behave consistently and plausibly?

**Measurement Validation:** Does the evaluator measure the intended therapist competencies?

**Educational Effectiveness:** Does using TheraSim improve actual learning or therapeutic skills?

These are separate research objectives requiring different study designs.

---

## 30. Final Implementation Readiness Criteria

The testing architecture is ready for implementation when:

1. Core software requirements are linked to test cases.
2. Agent input and output contracts are testable.
3. State transition rules have deterministic unit tests.
4. Patient Agent behavioral scenarios are defined.
5. Evaluator human-review procedures are defined.
6. Event extraction annotation guidelines are established.
7. Security boundaries have testable acceptance criteria.
8. Persian and English test cases are available.
9. Benchmark configuration is versioned.
10. Model execution metadata is recorded.
11. Historical benchmark results can be compared.
12. Limitations are explicitly reported.

---

**End of Document**