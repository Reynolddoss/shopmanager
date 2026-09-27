#!/usr/bin/env bash
# macOS/Linux helper — runs tests + frontend; full Setup.exe still needs Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}"
if [[ -z "${PYTHON}" || ! -x "${PYTHON}" ]]; then
  if [[ -x "$HOME/.virtualenvs/shopmanager/bin/python" ]]; then
    PYTHON="$HOME/.virtualenvs/shopmanager/bin/python"
  elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PYTHON="$ROOT/.venv/bin/python"
  else
    PYTHON="python3"
  fi
fi
exec "$PYTHON" "$ROOT/scripts/buildSoftware.py" "$@"
