# ADR-0001 — SQLite Persistence and Migration Strategy

**Date:** 2026-11-16
**Status:** Accepted
**Scope:** Initial TheraSim local prototype

## Context

TheraSim requires an operational store and a logically separate restricted
case store. The application is a local single-user modular monolith.

The implementation baseline specifies Python's standard `sqlite3` module,
explicit repository interfaces, and separate migration histories.

## Decision

1. Use Python's standard-library `sqlite3`; do not introduce an ORM in this phase.
2. Store operational records in `data/therasim.db`.
3. Store restricted case records in `data/case_vault.db`.
4. Keep both databases outside the publicly served frontend directory.
5. Maintain independent SQL migration directories and migration histories.
6. Record SHA-256 checksums for applied migrations.
7. Enable SQLite foreign-key enforcement on every connection.
8. Use short explicit transactions and parameterized SQL.
9. Never hold a SQLite write transaction open while waiting for LLM generation.
10. Do not create databases merely by importing the FastAPI application.

## Consequences

The persistence layer remains small, dependency-light, and suitable for local
execution. Cross-database references must be validated by application services.
Separate files provide logical separation, not protection against a local
administrator or another process with unrestricted filesystem access.

Specialized repositories and higher-level services will be added in subsequent
implementation steps.
## Automatic initialization at application startup

- FastAPI uses its lifespan hook to initialize the operational and restricted SQLite databases before serving requests.
- Database initialization is idempotent. Existing data is preserved, and only unapplied migrations are executed.
- The data directory is resolved through `THERASIM_DATA_DIR`, falling back to the project-level `data` directory.
- Database files are local runtime artifacts and must not be committed to version control.
- Startup fails when database initialization or migration application fails.
- The CLI remains available for explicit development and maintenance operations.
