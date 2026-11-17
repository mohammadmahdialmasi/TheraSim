# TheraSim

**A local-first research prototype for psychotherapy-skills simulation**

TheraSim is an educational software project for practicing therapist-client
conversations with fictional clients. It combines a local FastAPI service, a
React interface, SQLite persistence, and optional local language-model
providers.

> **Scope and safety:** TheraSim is for research and education with synthetic
> cases only. It does not provide psychotherapy, diagnosis, clinical advice,
> supervision, certification, or a validated measure of therapist competence.

## Current implementation status

The repository contains a working local simulation workflow: case and run
management, sequential sessions with no universal count limit, model-assisted
patient interactions, immutable completed transcripts, and review-gated
evidence-linked memory proposals. The database uses versioned migrations and
keeps operational records separate from restricted case material.

Important limitations:

- ACT is the only supported modality. Other approaches are not executable.
- Session-planning policies are recorded configuration. Versioned treatment
  plans and evidence-linked, review-gated revisions are available, but an
  engine that automatically adapts plans from longitudinal progress is not
  implemented.
- The ACT rubrics are experimental and have not been clinically or
  psychometrically validated.
- A separate local-model-backed ACT session Evaluator Agent provides
  experimental formative feedback when a model is configured. It validates
  competency coverage and exact therapist-message quote references, saves
  immutable `requires_review` revisions, and does not claim semantic evidence
  validity or clinical/psychometric validity. Without a configured model,
  evaluation generation is unavailable; invalid model output is not saved.
  A separate experimental longitudinal evaluator analyzes every completed
  session in a Run (minimum two), requires scored competencies to cite evidence
  from at least two sessions, and preserves transcript and run-session
  provenance. Reports become stale when the Run's session snapshot changes.
  Older placeholder reports are preserved but their ratings are withheld by
  the API. Authenticated reviewers can append acceptance or revision-request
  feedback; review history does not mutate the generated report.
- Interaction-scoped model-assisted event and character-state proposals are
  extracted with exact patient-message evidence. Events and state transitions
  remain review-pending until explicitly reviewed. Event review is available
  through the sessions workspace and backend API. Deterministic cross-session
  memory consolidation suggestions preserve source snapshots and transcript
  references and remain pending human review; they do not overwrite source
  memories.
- Persian and English are available in parts of the interface, but complete
  localization and RTL/LTR validation are incomplete. A session evaluation
  panel displays reports and transcript evidence, and the run workspace
  displays longitudinal reports, cross-session evidence, provenance, and stale
  status. A standalone evaluation dashboard is not implemented. The Sessions
  workspace includes persisted Run analytics, compatible rubric-scoped raw
  rating-code comparisons, an evidence-linked chart, and a research-oriented
  JSON export.
- The Windows launcher runs development servers; there is no desktop installer
  or production distribution bundle yet.

See [docs/IMPLEMENTATION_BASELINE.md](docs/IMPLEMENTATION_BASELINE.md) for
verified implementation notes and gaps.

## Purpose and research direction

Trainees need safe opportunities to rehearse difficult conversations and
reflect on what they said. TheraSim explores how fictional clients, explicit
information boundaries, longitudinal continuity, and transcript-linked
formative feedback might support that practice. The current software is a
technical prototype, not evidence that these methods improve clinical
outcomes.

The initial scenario is the fictional ACT case AVA-001. It is an example, not
a fixed treatment course; runs may continue for any positive number of
sequential sessions.

## Architecture

TheraSim is a modular monolith:

```text
React + TypeScript frontend
            |
       FastAPI /api/v1
            |
  application services and agents
       |                |
operational SQLite   restricted SQLite
       |
optional local inference provider
```

- **Backend:** Python, FastAPI, Pydantic, SQLite, and Uvicorn.
- **Frontend:** React, TypeScript, and Vite.
- **Persistence:** `data/therasim.db` for operational data and
  `data/case_vault.db` for restricted case information. Migrations are kept
  under `backend/app/persistence/migrations/`.
- **Local inference:** Ollama or LM Studio through the Backend's
  OpenAI-compatible client. A provider and model are optional for startup, but
  required to generate simulated patient responses.
- **Agents:** The Patient Agent runs with an explicitly constructed context.
  A separate Evaluator Agent assesses completed ACT session transcripts when
  configured; both agents use the local model provider.

See [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md),
[docs/SECURITY_BOUNDARIES.md](docs/SECURITY_BOUNDARIES.md), and
[docs/adr/](docs/adr/) for design decisions. These documents describe intended
controls as well as implementation; check the baseline before assuming a
specified feature exists.

Paired SQLite backup and restore instructions are in
[docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md).

## Sessions, planning, and modalities

Sessions are created in sequence and may continue without a global maximum.
An earlier session must be completed before the next is created. Runs can be
interrupted and resumed. The API stores a planning-policy identifier such as
flexible, goal-based, milestone-based, or open-ended, but does not yet execute
a treatment-planning engine that autonomously rewrites a plan. Versioned
initial plans and evidence-linked, human-proposed revisions are supported; a
revision must be approved before becoming active. A limited deterministic
assessment now flags newly accepted setbacks, contradictions, or
progress-related events for human review. It does not infer outcomes, choose
clinical interventions, or change a plan automatically.

The initial case and protocol use ACT. The data model records modality and
protocol versions, and a backend registry contract now describes modality
protocol and rubric references. ACT is the only runnable modality and remains
partial. Registering another approach does not make it runnable; CBT, DBT,
CFT, MBCT, MBSR, Schema Therapy, Psychodynamic Therapy, EFT, and MCT remain
unavailable.

## Memory and evaluation

Persisted therapist/patient exchanges enqueue durable memory-extraction jobs.
When a local model is configured, a worker processes proposals with leases and
bounded retries. Evidence validation and explicit review gate whether a
proposal becomes active. The sessions interface includes memory review.
The review workspace also proposes related memories across sessions using
deterministic text overlap and a conservative negation hint. A reviewer must
write and approve every consolidation proposal; source memories and transcript
evidence remain preserved. These hints are not verified clinical conclusions.
Reviews are attributed to the authenticated local reviewer account; the
single-user account is not a multi-user authorization system.
Patient context retrieval now ranks active memories deterministically by
current-turn token relevance, evidence support, recency, confidence, and
memory scope; unrelated episodic entries without topical overlap are omitted.
This does not provide semantic embeddings or automatic contradiction
resolution.

The optional post-interaction extractor proposes behavioral/emotional events
and character-state transitions from only the completed exchange. Exact patient
quotes are checked against the source transcript, and proposals are stored as
`requires_review`; they do not automatically change approved character state.
Each extraction job pins the character-state snapshot that existed when the
interaction was saved, preventing later state from leaking into delayed work.
Migration `011_memory_extraction_state_context` adds this nullable reference;
legacy jobs without a pinned snapshot remain processable but cannot produce a
state transition proposal. Event reviews are append-only and preserve the
authenticated reviewer ID; the initial implementation supports one local
reviewer account and does not provide password reset.
The sessions workspace presents proposed events, observed reports, model
interpretations, source excerpts, and rationale-based accept/reject actions.
It also supports a versioned Run plan, goal display, and evidence-linked plan
revision proposals with approval/rejection history. These capabilities are
review-gated workflows. Deterministic adaptation guidance is based only on
newly accepted events; it is not clinically validated or an autonomous planner.

The versioned ACT session rubric is `ACT_RUBRIC_V0` 0.2. The current,
count-agnostic longitudinal rubric is `ACT_LONGITUDINAL_RUBRIC_V0` 0.2;
version 0.1 is retained as a historical three-session example. Neither rubric
is validated. Session evaluation reports are experimental, transcript-linked
and require human review; no semantic evidence judgment is guaranteed.
Without a configured Evaluator Agent, generation returns
`503 evaluator_unavailable_experimental`; invalid output returns `502` and is
not persisted as a report. Longitudinal evaluation is also experimental:
therapist-message references and excerpts are checked against the exact
transcripts, but semantic support for a rating is not established. Reports are
immutable, review-required revisions over all completed sessions in the Run
(at least two), with transcript hashes and a snapshot of all Run sessions.
Subsequent session creation, status changes, or transcript changes mark a
report stale. The Run workspace displays these reports and their referenced
source messages. Persisted Run analytics and JSON export include source
identifiers, event/memory/state counts, treatment-plan status, and evaluation
staleness. The workspace also lists raw session-level competency observations,
grouped by rubric version with confidence, missing-session reasons, evaluation
IDs, and evidence-message IDs. It does not calculate averages or claim
ratings are not averaged across rubric versions or represented as clinical
outcomes. The workspace provides a session-range-filtered chart only within an
exact rubric version and content hash; numeric codes are plotted as raw
observations, while NE and missing data are omitted and separately counted.
This descriptive comparison is not a validated competency trend. Exports omit
transcript and case text but still contain sensitive operational identifiers.

## Windows quick start

### Prerequisites

- Windows 10/11.
- Python 3.11 or newer.
- Node.js LTS with npm.
- Optional: Ollama or LM Studio and a compatible chat model for simulated
  patient interactions.

1. Install Python and Node.js if needed.
2. From the repository root, double-click `START_THERASIM.bat`.
3. On first run, approve the prompts to create the Python virtual environment
   or install missing dependencies. Dependency installation may need network
   access; already-installed dependencies are reused.
4. The launcher applies safe database migrations and idempotently seeds
   AVA-001. It does not reset or delete existing databases.
5. The browser opens at <http://127.0.0.1:5173>. Backend API documentation is
   at <http://127.0.0.1:8000/docs>.
6. On first browser access, create the single local reviewer account with a
   password of at least 12 characters. Later access requires signing in again
   after the browser session closes or the eight-hour token expires.
7. Create a simulation run, start it, add sessions as needed, and submit
   therapist messages. A local model must be configured for patient replies.
8. Double-click `STOP_THERASIM.bat` to stop only the Backend and Frontend
   processes started by this launcher. `CHECK_THERASIM.bat` checks local
   prerequisites and project dependencies.

The launcher logs are stored under `%LOCALAPPDATA%\TheraSim\logs`; process
ownership records are under `%LOCALAPPDATA%\TheraSim\runtime`. If startup
fails, inspect those logs and the error shown by the launcher.

### Manual development setup

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
Set-Location frontend
npm ci
```

In separate terminals, initialize the databases and start the services:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.persistence.cli
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

If the virtual environment is at the repository root, from `backend` its
Python path is `..\.venv\Scripts\python.exe` (one parent directory).

## Configuration

Configuration is read from the process environment; `.env` files are not
automatically loaded. For example, set these in PowerShell before starting the
Backend:

```powershell
$env:THERASIM_LLM_PROVIDER = "ollama"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
$env:OLLAMA_MODEL = "your-installed-model"
$env:THERASIM_LLM_TIMEOUT = "120"
```

For LM Studio use `THERASIM_LLM_PROVIDER=lm_studio`, set
`LM_STUDIO_BASE_URL` (default `http://127.0.0.1:1234/v1`) and
`LM_STUDIO_MODEL`. Provider credentials are optional local configuration and
must not be committed or embedded in a URL. Provider URLs must use HTTP(S) and
cannot contain user-info, query strings, or fragments; the provider catalog
shows only the origin. `THERASIM_DATA_DIR` can select a different local data
directory; otherwise the repository's ignored `data/` directory is used.
The launcher does not overwrite configuration files or install model runtimes.

## Tests and development

Run the Backend test suite from the `backend` directory:

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

Run Frontend checks from `frontend`:

```powershell
npm run lint
npm run build
```

Tests use local SQLite databases in temporary directories. Ordinary Backend
tests do not require a cloud API or local model. See
[docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md).

## API and database

The REST API is versioned under `/api/v1`; OpenAPI documentation is available
at `/docs` while the Backend is running. Database initialization and migration
are safe to repeat:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.persistence.cli
```

Before manually copying a database for backup, stop TheraSim. Copy both
databases using the backup command, which validates and bundles them without
overwriting an existing backup:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.persistence.backup_cli backup
```

For restore instructions and limitations, see
[docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md). Do not remove either
database to troubleshoot startup. Migrations should be tested against isolated
temporary databases before upgrading an important local dataset.

## Troubleshooting

- **Python or Node.js not found:** install the prerequisite and reopen the
  launcher. `CHECK_THERASIM.bat` reports missing tools.
- **Dependency install fails:** confirm network access, then rerun the
  launcher. It will reuse a completed virtual environment or `node_modules`.
- **A port is already in use:** the launcher will not terminate an unowned
  process. Close the service you started yourself or change its port
  configuration deliberately.
- **Backend starts but simulation replies fail:** configure a reachable local
  inference provider and model. The Backend can start without one.
- **Database migration error:** preserve both database files and the logs;
  do not delete or reset local data.
- **Launcher shutdown:** use `STOP_THERASIM.bat`; it verifies saved process ID,
  start time, executable, and command line before stopping a process.

## Security, privacy, and limitations

The application binds its development servers to loopback. SQLite separation
is logical, not operating-system access control. A single local reviewer
account protects the API, but multi-user authorization, password reset, and
database encryption at rest are not implemented. Encrypted backups are
available as an explicit passphrase-protected option; ordinary backups remain
unencrypted. Login attempts are throttled per
hashed client address after five attempts in a 15-minute window. Local-model
requests/transcripts should be treated as sensitive even though this prototype
is designed for synthetic data. Do not enter real client information. Review
[docs/SECURITY_BOUNDARIES.md](docs/SECURITY_BOUNDARIES.md) before deployment;
this repository is not production-ready.

Known gaps include semantic evaluation validity, interpretation of raw analytic
comparisons, complete event processing, complete localization, encrypted
database storage, automated retention, and desktop packaging.

## Release status and roadmap

The intended near-term work is independent evaluator validation and review,
compatible longitudinal evaluation interpretation, further memory/event
lifecycle completion, bilingual accessibility, and integration testing. A Windows
installer is only a proposed architecture; a reproducible installer has not
been built or tested. Current release preparation is source-based, and no
release has been published.

See [CHANGELOG.md](CHANGELOG.md) and
[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

## License and citation

Original project documentation, specifications, rubrics, and scenarios are
licensed under CC BY 4.0 as described in [LICENSE.md](LICENSE.md). That file
does not establish license terms for future executable software or third-party
materials. See [COPYRIGHT.md](COPYRIGHT.md) and [CITATION.cff](CITATION.cff)
for attribution and citation metadata.
