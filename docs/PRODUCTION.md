# Production operations — MM Electricals Phase 5

## Production architecture

Django owns SQLite; the UI never opens the database file. In development, Vite (`:5173`) proxies `/api` and `/media` to `runserver` (`:8000`).

In the installed app:

1. `MM Electricals.exe` (Tauri) shows a splash page and starts `resources\api\mm-electricals-api.exe --port 48620` with no console window. If 48620 is taken, it uses any free port.
2. The API (PyInstaller folder build) runs `safe_upgrade`, then a due scheduled backup, then serves Django with Waitress on `127.0.0.1` only. `DEBUG` is off and the secret key is generated per install.
3. When the port answers, the window navigates to `http://127.0.0.1:<port>/`. Django serves the built React UI, `/api/v1/` and `/media/` from one origin.
4. Closing the app stops the API. If the app crashes or is killed, the API notices that its parent process is gone and exits by itself.
5. A second launch focuses the existing window instead of starting another API.

Installed layout:

- `%LOCALAPPDATA%\Programs\MM Electricals\` (per-user install): app exe plus `resources\api\` (Python, Django, built UI).
- `%LOCALAPPDATA%\MMElectricals\`: live SQLite, `secret_key.txt`, `media\` (product photos), `backups\`, `logs\`.

Runtime switches (read by `backend/config/runtime.py`): `MM_PACKAGED=1` (set by the launcher), `MM_DEBUG`, `MM_DATA_DIR`, `MM_SECRET_KEY`, `MM_FRONTEND_DIST`.

## Troubleshooting a shop PC

- If startup fails, the splash page shows the reason and the log path.
- `logs\api.log`: API start, upgrades, backups and request errors. It rotates to `api.log.1` above 5 MB.
- `logs\api-console.log`: crashes that happen before Python logging starts (e.g. a damaged install).
- To run the API by hand in a terminal: `"%LOCALAPPDATA%\Programs\MM Electricals\resources\api\mm-electricals-api.exe" --console --port 48621`, then open `http://127.0.0.1:48621/`.

## Backup

`SnapshotBackupService.create_snapshot` writes `backups/<stamp>/database/mm_electricals.sqlite3`, CSV extras, and `metadata.json`. SQLite `integrity_check` must return `ok` or the snapshot is rejected. Retention uses `ApplicationSettings.backup_retention_count`.

Manual: Settings → Backup now, or `python manage.py backup_database`.

Daily/weekly: enable `scheduled_backup_enabled`. The check runs every time the app starts (and when Settings loads), and a backup is taken when the last one is older than the schedule. A failed scheduled backup is logged but does not block the shop from opening.

## Restore

1. Validate backup integrity.
2. Snapshot the live file (`pre_restore_safety`).
3. Operator confirms in Settings.
4. Copy backup over live SQLite.
5. Integrity-check again; on failure copy the safety snapshot back.

`python manage.py restore_database <folder> --confirm`

## Upgrade

The installed app runs `safe_upgrade` on every start:

- On a new install it creates the database; there is nothing to back up yet.
- When the schema is already current it does nothing, so routine launches don't push real backups out of retention.
- When migrations are pending it takes a backup, migrates and runs an integrity check, and restores the pre-upgrade snapshot on failure.

Installing a newer `Setup.exe` over the old one keeps `%LOCALAPPDATA%\MMElectricals\` untouched.

## Printing

`GET /api/v1/sales/<id>/print/?kind=a4|thermal` returns HTML. The UI loads it into a hidden iframe (`frontend/src/utils/printHtml.ts`, no popup windows) and the OS print dialog chooses A4 vs 80mm. Totals stay in `InvoicePayloadService`.

## Security

Loopback-only middleware. No shelling out to user paths. Restore folder names cannot contain `..`.

## Windows installer build

Use the single script (on a Windows builder with Python, Node, Rust):

```
scripts\buildSoftware.bat
```

or `python scripts\buildSoftware.py`. Output: `desktop\src-tauri\target\release\bundle\nsis\*-setup.exe`.

Steps:

1. Run the tests.
2. Build the React UI.
3. Build the PyInstaller folder app with the UI inside.
4. Smoke test: start the frozen API on a throwaway data folder and check `/api/v1/health/` plus `/sales`.
5. Copy the result into `desktop/src-tauri/api-bundle/`.
6. `tauri build` (NSIS).

`python scripts/buildSoftware.py --api-only` runs steps 1–5 on macOS/Linux too.

The installer is unsigned for now, so Windows SmartScreen shows "Windows protected your PC". Click **More info → Run anyway**. Code signing is a later stage.
