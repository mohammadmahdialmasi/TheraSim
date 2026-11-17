# Changelog

Notable project changes are recorded here. This prototype does not yet publish
versioned releases.

## Unreleased

- Added a Windows development launcher with opt-in dependency setup, safe
  database initialization, loopback-only servers, process ownership checks,
  logs, and a separate stop command.
- Replaced the Frontend template README with project-specific setup and status
  guidance.
- Disabled deterministic placeholder evaluation generation. Evaluation
  requests now report that the Evaluator Agent is unavailable; historical
  placeholder records remain stored but are exposed as experimental without
  their ratings or evidence.
- Aligned longitudinal ACT competency identifiers with rubric version 0.2.
- Expanded ignore rules for local caches, SQLite sidecars, and generated test
  output.

## 0.1.0 — 2026-11-14

- Initial citation metadata; this is not a published application release.
