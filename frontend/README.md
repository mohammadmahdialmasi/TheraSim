# TheraSim Frontend

The TheraSim user interface is a React and TypeScript application built with
Vite. It communicates with the local FastAPI Backend; it does not connect
directly to SQLite or to Ollama/LM Studio.

## Requirements

- Node.js LTS and npm.
- The TheraSim Backend running at `http://127.0.0.1:8000`.

For the Windows-first local workflow, use `START_THERASIM.bat` from the
repository root. It checks dependencies, offers safe setup when dependencies
are missing, initializes the local databases, starts the Backend and Vite, and
opens the application. Use `STOP_THERASIM.bat` to stop only its own processes.

## Manual development

From this directory:

```powershell
npm ci
npm run dev -- --host 127.0.0.1
```

The development server is available at <http://127.0.0.1:5173>. To verify the
Frontend:

```powershell
npm run lint
npm run build
```

## Current interface

Implemented screens include the dashboard, local model laboratory, therapy
approach overview, and simulation sessions with transcript and memory-review
controls. Several navigation destinations remain roadmap/placeholder views.
Evaluation reports, therapist analytics, evidence-linked charts, and complete
Persian/English localization are not implemented. Persian is used in parts of
the interface; do not assume all routes or content have complete RTL/LTR
coverage.

API calls are centralized in `src/lib/api.ts` and feature modules under
`src/features/`. Shared English/Persian strings are in `src/i18n.ts`; the
sessions workflow has feature-specific copy. This arrangement is not yet a
complete localization system and currently has no automated missing-key
check.
