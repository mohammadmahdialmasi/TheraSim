# Source Release Readiness Checklist

This checklist is for a future release review. It does not declare the current
repository release-ready.

## Before preparing an archive

- [ ] Review all staged, unstaged, and untracked changes; do not include local
  databases, virtual environments, dependency folders, logs, or secrets.
- [ ] Confirm ownership, attribution, software licensing, scenario licensing,
  and third-party dependency notices.
- [ ] Review the release notes, citation, README instructions, and supported
  Python/Node versions.
- [ ] Create a clean source checkout and verify dependency installation from
  lock files.
- [ ] Run the complete Backend test suite, Frontend lint, TypeScript build,
  migration checks, and launcher checks.
- [ ] Exercise a clean local startup, run creation, variable sequential
  sessions, interactions with a deterministic fake model, database
  persistence, and launcher shutdown.
- [ ] Verify evaluation endpoints do not present placeholder output as an
  assessment. The Evaluator Agent and analytics remain blockers for any
  evaluation-capability claim.
- [ ] Review data separation, loopback binding, logging, reviewer identity,
  dependency advisories, and database backup/recovery. Do not equate passing
  tests with a security audit.
- [ ] Verify the archive contains no user data, local model, `.env`, secrets,
  virtual environment, or generated dependency/build output.

## Current assessment

This is a research prototype, not a production or clinical release. The
Windows launcher is source-based and depends on Python and Node.js installed
on the user's system. It has not been validated on a clean Windows machine.
There is no packaged desktop application, signed installer, Evaluator Agent,
complete bilingual interface, or complete analytics experience.

Do not publish an installer, GitHub Release, tag, or commit as part of this
checklist without separate authorization.
