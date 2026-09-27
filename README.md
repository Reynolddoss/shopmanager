# MM Electricals

Windows-bound inventory and shop management for an electrical retailer. Phase 1 is foundation only: Django API, SQLite, React shell, Tauri wrapper.

## Python environment

Use the existing virtualenv (do not create another):

```bash
source ~/.virtualenvs/shopmanager/bin/activate
```

## Start (development)

Terminal 1 — API:

```bash
cd backend
~/.virtualenvs/shopmanager/bin/python manage.py runserver 127.0.0.1:8000
```

Terminal 2 — UI:

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` to Django.

Tauri (requires a Rust toolchain via rustup):

```bash
cd desktop
npm install
npm run tauri dev
```

## Tests and checks

```bash
~/.virtualenvs/shopmanager/bin/pytest
cd frontend && npm run build && npm run lint
```

## Production (Windows installer)

You need a **Windows Setup.exe** to share with shop PCs. That file is built on Windows
(or via GitHub Actions) — not on macOS.

### Easiest from a Mac: GitHub Actions

1. Commit and push this repo to GitHub.
2. On GitHub: **Actions** → **Build Windows installer** → **Run workflow**.
3. When it finishes, download the artifact **MM-Electricals-Windows-Setup**.
4. Share the `*-setup.exe` file with the Windows user (they run the installer once).

### Or build on a Windows PC

```bat
scripts\buildSoftware.bat
```

Output: `desktop\src-tauri\target\release\bundle\nsis\*-setup.exe`

Shop data after install: `%LOCALAPPDATA%\MMElectricals\` (SQLite, backups, logs, photos).

To check the frozen API on a Mac/Linux machine (no installer): `python scripts/buildSoftware.py --api-only`.

To preview production mode without packaging, run `npm run build` in `frontend/`, start Django, and open http://127.0.0.1:8000/. Django serves the built UI itself.

See [docs/PRODUCTION.md](docs/PRODUCTION.md).

