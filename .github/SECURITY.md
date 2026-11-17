# Security policy

TheraSim is an experimental research/educational prototype and is not designed
or verified for production clinical use. Use synthetic data only. Do not send
real patient/client information, credentials, database files, or private logs
to the project.

## Reporting a suspected vulnerability

Please do not publish an unpatched vulnerability or sensitive reproduction
details in a public issue. If GitHub's private vulnerability reporting is
available for this repository, use the repository **Security** tab to submit
a private report. Otherwise, contact the repository maintainer through a
private contact route linked from the repository. Include only synthetic
examples and the minimum information needed to understand the issue.

The project is maintained on a best-effort basis. There is no guaranteed
response or remediation timeline, and no security support SLA.

## Scope and limitations

The app is intended for a single local user and binds development/desktop
services to loopback. Local binding is not a substitute for operating-system
security. Live SQLite files are not encrypted at rest; optional encrypted
backups protect backup copies only. Local model providers receive requests
sent to their configured endpoint. Dependencies and generated executables
must be reviewed in their own context. Passing automated tests or dependency
scans is not an independent security audit.
