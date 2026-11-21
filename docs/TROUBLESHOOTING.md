# TheraSim Troubleshooting

Use fictional data only. Do not send databases, raw logs, credentials,
transcripts, or real-person information in a public issue or support message.

## Application does not start

- Confirm that the ZIP was completely extracted and run
  `TheraSim\TheraSim.exe` from the extracted folder.
- The package is a portable one-folder distribution; do not move only the EXE
  away from its `_internal` resources.
- If the application reports a port conflict, close the other local service
  using port 8765 or start TheraSim with a free `THERASIM_PORT` value.
- Review `%LOCALAPPDATA%\TheraSim\logs\therasim.log`. Redact the log before
  sharing it; do not attach the database or provider settings.
- The app binds only to `127.0.0.1`; do not open its port to a network.

## Login and saved data

- On the first run, initialize the local reviewer account with a password
  between 12 and 1024 characters; the UI has a shorter practical entry limit.
- If login throttling is active, wait for the displayed interval instead of
  repeatedly retrying.
- The application stores `therasim.db` and `case_vault.db` under
  `%LOCALAPPDATA%\TheraSim\data`. Do not delete or replace them to troubleshoot
  a UI problem.
- Before moving data or restoring a backup, stop TheraSim and follow
  [Backup and restore](BACKUP_RESTORE.md). Restore is intended for a new
  destination and does not overwrite existing data.

## Local model connection

- Follow the complete [Ollama setup guide](OLLAMA_SETUP.md).
- Confirm the selected provider, model tag, host, port and `/v1` base path in
  **Settings**; run **Test connection** after changes.
- Confirm Ollama responds at
  `http://127.0.0.1:11434/api/version` and that the model appears in
  `ollama list`.
- Keep local-only mode enabled for loopback inference. A remote endpoint is
  blocked unless the user explicitly enables remote mode and confirms it.
- Restart TheraSim after changing provider settings used by the simulation
  agents.
- A model listing may be unsupported on some compatible servers. Enter the
  exact installed model name manually if the provider allows it.
- For slow requests, inspect `ollama ps` and available memory. TheraSim's
  provider timeout defaults to 120 seconds and can be set from 1 to 600.

## Language, layout, and exports

- Use the English/Persian switch in the application. The selected language is
  stored in browser local storage.
- If an older browser tab shows stale text, reload the page after saving.
- For support exports, wait for the privacy preview, check the selected
  language, inspect the displayed fields, and explicitly confirm before
  downloading. The app does not send the archive automatically.
- Review the archive before attaching it to any message. Never include a
  database, transcript, case document, credential, or raw log.

## Backup, restore, or update questions

- A model download and the initial application download need internet; local
  inference with already downloaded model weights does not.
- The update metadata check is manual/read-only and does not update files.
- Do not replace an application folder while it is running. Extract a new
  application version separately and keep the existing user-data directory.
- For backup commands and encryption behavior, see
  [Backup and restore](BACKUP_RESTORE.md).

## Report a problem safely

1. Note the TheraSim version, Windows version, selected provider/model tag,
   and the exact non-sensitive error.
2. Reproduce the issue with a synthetic case if possible.
3. Use the in-app support preview and manually inspect the diagnostics ZIP.
4. Remove personal data and secrets before sharing anything.
5. Use the repository's [support policy](../.github/SUPPORT.md) or
   [security reporting policy](../.github/SECURITY.md), as appropriate.
