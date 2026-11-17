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
- Run planning policies are recorded configuration; a treatment-planning
  engine that recommends or approves plan changes is not implemented.
- The ACT rubrics are experimental and have not been clinically or
  psychometrically validated.
- The Evaluator Agent is **not implemented**. Evaluation-generation requests
  report an experimental/unavailable status instead of saving placeholder
  scores. Older placeholder reports are preserved in the database but are
  labeled experimental and their ratings are withheld by the API.
- Behavioral event extraction, treatment-state transitions, and autobiographical
  memory consolidation are incomplete.
- Persian and English are available in parts of the interface, but complete
  localization, RTL/LTR validation, analytics, evidence-linked charts, and
  evaluation reports are not complete.
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
  The Evaluator Agent is a future component and is not currently available.

See [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md),
[docs/SECURITY_BOUNDARIES.md](docs/SECURITY_BOUNDARIES.md), and
[docs/adr/](docs/adr/) for design decisions. These documents describe intended
controls as well as implementation; check the baseline before assuming a
specified feature exists.

## Sessions, planning, and modalities

Sessions are created in sequence and may continue without a global maximum.
An earlier session must be completed before the next is created. Runs can be
interrupted and resumed. The API stores a planning-policy identifier such as
flexible, goal-based, milestone-based, or open-ended, but does not yet execute
a treatment-planning engine or automatically change a plan. Fixed-length
protocols, approvals, and explicit plan revisions remain future work.

The initial case and protocol use ACT. The data model records modality and
protocol versions, but there is no implemented multi-modality registry. CBT,
DBT, CFT, MBCT, MBSR, Schema Therapy, Psychodynamic Therapy, EFT, and MCT are
not available simulation modules and must not be selected as if implemented.

## Memory and evaluation

Persisted therapist/patient exchanges enqueue durable memory-extraction jobs.
When a local model is configured, a worker processes proposals with leases and
bounded retries. Evidence validation and explicit review gate whether a
proposal becomes active. The sessions interface includes memory review and
shows that reviewer identity is unverified in this single-user, unauthenticated
prototype. This is not a multi-user authorization system.

The versioned ACT session rubric is `ACT_RUBRIC_V0` 0.2. The current,
count-agnostic longitudinal rubric is `ACT_LONGITUDINAL_RUBRIC_V0` 0.2;
version 0.1 is retained as a historical three-session example. Neither rubric
is validated. Since there is no Evaluator Agent, generation endpoints return
`503 evaluator_unavailable_experimental` and create no report. Charts,
comparisons, trends, response timelines, and report recommendations are not
implemented.

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
6. Create a simulation run, start it, add sessions as needed, and submit
   therapist messages. A local model must be configured for patient replies.
7. Double-click `STOP_THERASIM.bat` to stop only the Backend and Frontend
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
must not be committed. `THERASIM_DATA_DIR` can select a different local data
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
`data\therasim.db` and `data\case_vault.db` together to a dated backup folder;
do not remove either database to troubleshoot startup. Migrations should be
tested against a copy before upgrading an important local dataset.

Example from the repository root after stopping the application:

```powershell
$backup = Join-Path $PWD ("backups\" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $backup | Out-Null
Copy-Item .\data\therasim.db, .\data\case_vault.db -Destination $backup
```

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
is logical, not operating-system access control. The local API has no
multi-user authentication, the memory reviewer is not authenticated, and
local-model requests/transcripts should be treated as sensitive even though
this prototype is designed for synthetic data. Do not enter real client
information. Review [docs/SECURITY_BOUNDARIES.md](docs/SECURITY_BOUNDARIES.md)
before deployment; this repository is not production-ready.

Known gaps include the Evaluator Agent, longitudinal evaluation revisions and
scope selection, evidence-linked analytics, complete event processing,
memory consolidation, authenticated review, complete localization, automated
backup/recovery, and desktop packaging.

## Release status and roadmap

The intended near-term work is evaluator implementation and validation,
longitudinal evaluation, memory/event lifecycle completion, bilingual
accessibility, analytics, and integration testing. A Windows installer is only
a proposed architecture; a reproducible installer has not been built or
tested. Current release preparation is source-based, and no release has been
published.

See [CHANGELOG.md](CHANGELOG.md) and
[docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

## License and citation

Original project documentation, specifications, rubrics, and scenarios are
licensed under CC BY 4.0 as described in [LICENSE.md](LICENSE.md). That file
does not establish license terms for future executable software or third-party
materials. See [COPYRIGHT.md](COPYRIGHT.md) and [CITATION.cff](CITATION.cff)
for attribution and citation metadata.
