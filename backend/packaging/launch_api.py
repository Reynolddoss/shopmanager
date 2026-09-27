"""
Packaged API entry point (`mm-electricals-api.exe`, built by PyInstaller).

Started by the desktop shell with `--port N`. Upgrades the database safely,
runs a due scheduled backup, then serves Django (UI + API + media) with
Waitress on 127.0.0.1 only. Exits on its own when the desktop app goes away.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import traceback
from pathlib import Path


class LauncherArguments:
    """Command-line options passed by the desktop shell (or a developer testing by hand)."""

    DEFAULT_PORT = 48620

    def __init__(self, argv: list[str]) -> None:
        parser = argparse.ArgumentParser(prog="mm-electricals-api")
        parser.add_argument("--port", type=int, default=self.DEFAULT_PORT, help="Loopback port to serve on.")
        parser.add_argument("--data-dir", default=None, help="Override the shop data folder.")
        parser.add_argument("--console", action="store_true", help="Log to this console instead of logs/api.log.")
        parsed = parser.parse_args(argv)
        self.port: int = parsed.port
        self.data_dir: str | None = parsed.data_dir
        self.console: bool = parsed.console


class ApiLogFile:
    """Send stdout/stderr to <data>/logs/api.log, keeping one rotated copy."""

    MAX_BYTES = 5 * 1024 * 1024

    def __init__(self, log_dir: Path) -> None:
        self.path = log_dir / "api.log"

    def attach(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size > self.MAX_BYTES:
            self.path.replace(self.path.with_suffix(".log.1"))
        handle = open(self.path, "a", encoding="utf-8", buffering=1)
        sys.stdout = handle
        sys.stderr = handle
        return self.path


class ParentProcessWatchdog:
    """
    Exit when the desktop shell process ends.

    Covers crashes and Task Manager kills, where the shell never gets the
    chance to stop us; otherwise an orphan would keep the port and database open.
    """

    SYNCHRONIZE = 0x00100000
    INFINITE = 0xFFFFFFFF
    POLL_SECONDS = 2.0

    def __init__(self, parent_pid: int) -> None:
        self.parent_pid = parent_pid

    def start(self) -> None:
        threading.Thread(target=self._watch, name="parent-watchdog", daemon=True).start()

    def _watch(self) -> None:
        if os.name == "nt":
            self._wait_windows()
        else:
            self._poll_posix()
        print(f"Desktop app (pid {self.parent_pid}) exited; stopping API.", flush=True)
        os._exit(0)

    def _wait_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        handle = kernel32.OpenProcess(self.SYNCHRONIZE, False, self.parent_pid)
        if not handle:
            return
        kernel32.WaitForSingleObject(handle, self.INFINITE)
        kernel32.CloseHandle(handle)

    def _poll_posix(self) -> None:
        alive = lambda: self._posix_alive()
        while alive():
            time.sleep(self.POLL_SECONDS)

    def _posix_alive(self) -> bool:
        try:
            os.kill(self.parent_pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


class PackagedApiLauncher:
    """Prepare the environment, upgrade the database, and serve with Waitress."""

    WAITRESS_THREADS = 8

    def __init__(self, argv: list[str]) -> None:
        self.args = LauncherArguments(argv)

    def data_dir(self) -> Path:
        """Live shop data goes under LocalAppData, never next to the installed program."""
        override = self.args.data_dir or os.environ.get("MM_DATA_DIR")
        if override:
            return Path(override).expanduser().resolve()
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
            return base / "MMElectricals"
        return Path.home() / ".mm_electricals"

    def backend_root(self) -> Path:
        """PyInstaller puts the Django sources in _MEIPASS; from the repo it is backend/."""
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if getattr(sys, "frozen", False) and bundle_dir:
            return Path(bundle_dir)
        return Path(__file__).resolve().parents[1]

    def prepare_environment(self, data_dir: Path) -> None:
        backend = self.backend_root()
        os.chdir(backend)
        sys.path.insert(0, str(backend))
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        os.environ["MM_DATA_DIR"] = str(data_dir)
        os.environ["MM_PACKAGED"] = "1"
        list(map(lambda name: (data_dir / name).mkdir(parents=True, exist_ok=True), ("media", "backups", "logs")))

    def start_watchdog(self) -> None:
        parent_pid = os.environ.get("MM_PARENT_PID", "")
        if parent_pid.isdigit():
            ParentProcessWatchdog(int(parent_pid)).start()

    def run(self) -> int:
        data_dir = self.data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        if not self.args.console:
            ApiLogFile(data_dir / "logs").attach()
        print(f"--- MM Electricals API starting (port {self.args.port}, data {data_dir}) ---", flush=True)
        self.start_watchdog()
        try:
            self.prepare_environment(data_dir)
            import django
            from django.core.management import call_command

            django.setup()
            call_command("safe_upgrade")
            self.run_scheduled_backup(call_command)

            from waitress import serve

            from config.wsgi import application

            serve(application, host="127.0.0.1", port=self.args.port, threads=self.WAITRESS_THREADS)
            return 0
        except Exception:
            traceback.print_exc()
            sys.stdout.flush()
            return 1

    def run_scheduled_backup(self, call_command) -> None:
        """A failed routine backup is logged but must not stop the shop from opening."""
        try:
            call_command("run_scheduled_backup")
        except Exception:
            print("Scheduled backup failed (the app will still start):", flush=True)
            traceback.print_exc()


class LauncherMain:
    """Process entry so PyInstaller and `python launch_api.py` behave the same."""

    @staticmethod
    def main() -> None:
        sys.exit(PackagedApiLauncher(sys.argv[1:]).run())


if __name__ == "__main__":
    LauncherMain.main()
