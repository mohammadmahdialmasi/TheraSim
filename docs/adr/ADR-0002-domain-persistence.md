# ADR-0002 — Operational Domain Persistence

**Status:** Accepted
**Date:** 2026-11-16

## Context

Migration 001 established the operational core and the independent restricted case vault.
The logical schema requires the remaining disclosure, event, state, memory, rubric, and
evaluation tables in the operational database.

## Decisions

1. Migration 002 applies only to `therasim.db`. The restricted database schema remains
   unchanged.
2. Existing Migration 001 is immutable and remains checksum-verified.
3. Composite foreign keys enforce run/case-version and run/session consistency where
   those relationships are represented inside the operational database.
4. Event, transition, memory, and evaluation evidence records reference messages by
   foreign key. Validation that evidence belongs to the correct session/run remains an
   application-service responsibility where the logical schema does not carry enough
   columns for a composite constraint.
5. Related historical records use restrictive foreign-key behavior. No cascade deletion
   is introduced for transcripts, state history, memory, or evaluations.
6. Evidence offsets use Python Unicode code-point indices over the exact original text,
   without normalization. Start and end offsets must be supplied together and end must
   not precede start. API/frontend conversion must be tested separately.
7. SQL validates structural constraints. JSON payload/schema validation, restricted
   case-fact existence, disclosure-policy validation, rubric competency membership,
   and semantic evidence validation remain application responsibilities.

## Known contract gaps retained for a later decision

- `memory_items.memory_version` exists, but schema version 0.2 does not define a stable
  memory-series identifier or an explicit supersedes relationship. Memory Service
  implementation must resolve version lineage before relying on cross-session updates.
- Evaluation generation is described as idempotent, but schema version 0.2 does not
  define a durable evaluation-request idempotency record. This must be resolved before
  implementing evaluation request orchestration.
- Transcript version and hash lifecycle must be finalized before session completion
  and evaluation services are implemented. The evaluation transcript manifest must
  reference exact finalized versions.

## Consequences

- The operational database contains 25 domain tables plus `schema_migrations`.
- The restricted database continues to contain its two domain tables plus its own
  `schema_migrations`.
- New migrations must be additive unless an explicit backup and recovery plan approves
  a destructive change.
