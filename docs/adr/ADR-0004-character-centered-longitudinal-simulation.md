
# ADR-0004: Character-Centered Longitudinal Simulation

**Status:** Accepted for architectural implementation
**Date:** 2026-11-16

## Context

TheraSim requires synthetic clients to preserve identity and personality across multiple sessions while responding to actual conversational experiences.

The existing implementation already has:

- Separate operational and restricted databases.
- Versioned case definitions.
- Restricted case profiles and fact registries.
- Run-specific event, memory, and ACT-state persistence structures.
- A structured PatientContext builder.
- A Patient Agent that receives explicitly serialized context.
- Interaction idempotency and transcript persistence.

However, the existing architecture does not yet define a complete, versioned personality profile or a generic dynamic character-state model. It also does not provide a complete memory proposal, validation, and consolidation lifecycle.

## Decision

Adopt a character-centered longitudinal architecture with three distinct scopes:

1. Immutable, versioned personality profile per character/case version.
2. Dynamic psychological and interpersonal state per simulation run.
3. Run-specific events and source-linked memories.

The existing ACT state model remains separate.

The personality profile will be stored in the restricted case vault. Run-specific state, events, and memories will remain in the operational database.

The PatientContext service will assemble the exact profile version and authorized run history for Patient Agent execution.

The LLM may propose events, memories, and state changes. Backend services retain exclusive authority over validation and persistence.

No third primary LLM agent is introduced by this decision. Structured continuity extraction is an orchestrated, versioned operation and must not become an independent source of truth.

## Consequences

### Positive

- Stable character identity across sessions.
- Independent trajectories for repeated runs of the same character.
- Clear distinction between trait, state, event, and memory.
- Better provenance and auditability.
- Explicit protection against cross-run memory leakage.
- Compatibility with the existing local-first, two-database architecture.

### Costs

- New profile and state schemas.
- Additional repositories and services.
- PatientContext schema evolution.
- Additional model-output validation and memory lifecycle work.
- More demanding longitudinal tests.

## Rejected alternatives

### Prompt-only personality

Rejected because a long system prompt cannot reliably provide versioned, auditable, source-linked identity and memory.

### One mutable global character state

Rejected because independent runs must not influence one another.

### Treating ACT state as personality

Rejected because clinical-process constructs and broad personality traits represent different domains.

### Allowing the LLM to write canonical memories or state directly

Rejected because model output is untrusted and requires application-owned validation.

## Implementation status

This ADR establishes the intended architecture. It does not claim that the database migrations, service integration, UI, or longitudinal behavior are complete.

See `docs/CHARACTER_MODEL_SPEC.md`.
