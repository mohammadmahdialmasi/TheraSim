# TheraSim v0.3.1

TheraSim v0.3.1 is a local-first framework for psychotherapy skills simulation
and evidence-grounded ACT therapist evaluation.

## Included

- Repository and active-version consistency improvements.
- Automated CI validation for release-version metadata.
- Updated Windows x64 portable package workflow.
- Local Ollama and provider workflows.
- Separate patient-simulation and evaluator model configuration.
- Structured ACT evaluation and transcript/evidence validation.
- Hardware-aware compatibility guidance.

## Verification

The package and source are published only after the exact final commit has
passed backend tests, frontend tests and type checking, lint, production build,
dependency audits, security checks, Windows packaging, isolated smoke tests,
and the version-consistency gate.

## Scope and limitations

- ACT is currently the only runnable psychotherapy modality.
- This is experimental research and training software.
- Clinical effectiveness and psychometric validity have not been established.
- Model weights are not bundled.
- Compatibility beyond explicitly tested configurations has not been established.
