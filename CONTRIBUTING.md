# Contributing

TheraSim is an experimental research and educational prototype. Discussion,
bug reports, and documentation suggestions are welcome. Use fictional,
synthetic examples only; never submit client/patient data, credentials, local
database files, model weights, or private logs.

## Before proposing a change

1. Read `README.md`, `docs/SECURITY_BOUNDARIES.md`, `docs/MVP_DECISIONS.md`,
   and `LICENSE.md`.
2. Check existing issues and describe the user-facing problem, scientific
   limitations, and a way to verify the proposed behavior.
3. Keep changes within the ACT-only, local-first product scope. Do not claim
   clinical effectiveness, psychometric validity, or full offline operation
   without appropriate independent evidence.
4. Do not include generated databases, `.env` files, model weights, local
   configuration, screenshots containing real data, or unrelated backups.

## Source-code contribution terms

This repository is not offered under an open-source software license.
`LICENSE.md` covers only the specified documentation and research materials;
executable source code remains under the copyright holder's exclusive rights.
Opening an issue does not grant permission to copy, modify, or redistribute
source code. Before submitting a source-code patch or pull request, obtain
written permission from the maintainer and agree on the rights and terms for
that contribution. Do not infer a license for your contribution or the
existing source from the repository's CC BY 4.0 documentation license.

## Local checks

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
Set-Location ..\frontend
npm run lint
npm run build
```

Use a temporary data directory for manual runs and tests. Do not inspect or
reuse another user's local database. Include the relevant command and
redacted failure summary in an issue; never include secret values.
