# MM Electricals — production release helper
# Prefer: python scripts/buildSoftware.py  (or scripts\buildSoftware.bat on Windows)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/buildSoftware.sh" "$@"
