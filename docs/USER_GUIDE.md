# User guide

TheraSim is an experimental research and educational prototype for practising
skills with fictional simulations. It is not psychotherapy, diagnosis,
clinical advice, professional supervision, certification, or a validated
measure of competence. Do not enter real patient information.

## Start a local session

1. Start the application and open its local interface.
2. Create or sign in to the local reviewer account.
3. In **Settings**, inspect the provider endpoint and test the connection.
   The interface can be explored without a configured model, but model-backed
   patient responses and evaluation require an available provider/model.
4. Open a simulation, choose a fictional ACT scenario, and interact with the
   simulated client. ACT is the only runnable modality; other approaches shown
   in the interface are not implemented treatment modules.
5. Review the conversation and any generated evaluation critically. Reports
   are experimental, require human review, and do not establish clinical,
   psychometric, or therapeutic validity.

## Models and evaluation

The patient agent and ACT evaluator may use separate model IDs. If a role
specific model is blank, it uses the provider's general model. The same
provider endpoint is shared; role selection does not imply separate processes
or separate privacy boundaries. Memory extraction follows the patient model.
After saving provider/model settings, restart the application if needed so
agent instances load the changes.

Ollama evaluator requests may use constrained JSON output, but this is not a
reliability guarantee. The application still validates the report structure,
rubric values, transcript speakers, and evidence quotes, rejecting malformed
or unsupported evidence. The checked-in model evaluation records failures as
well as successes; no evaluator model is recommended.

Hardware inventory is optional and user-initiated. It reports limited
observations and estimates; it does not select, download, or certify a model
for every device. Compatibility must be tested for the actual model, provider,
context, and workload.

## Privacy and data

The default desktop app binds to loopback. Model requests go to the endpoint
shown in Settings. A remote endpoint is possible only after changing the
local-only setting and explicitly confirming remote use. Confirm the endpoint
before sharing any text.

The local account is a single-reviewer convenience, not a multi-user access
control system. SQLite databases are not encrypted at rest by the application.
Protect the operating-system account and device, and use the documented
backup/restore process before upgrading or moving the app. Support diagnostics
are previewed and user-initiated; inspect the contents before sharing.

## Language, versions, and updates

Select English or Persian in the interface. The Settings page shows the
installed application version and can check official release metadata. Update
checking is manual: it does not install or overwrite files. Download releases
only from the official GitHub Releases page, verify the supplied checksum, and
follow the installation guide. Back up application data before replacing the
portable application directory.

For installation see [Installation](INSTALLATION.md); for data recovery see
[Backup and restore](BACKUP_RESTORE.md); for system and security boundaries
see [Project architecture](PROJECT_ARCHITECTURE.md) and
[Security boundaries](SECURITY_BOUNDARIES.md).
