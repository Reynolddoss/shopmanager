"""
buildSoftware — one entry point to produce the installable shop app.

On Windows this script:
  1. Runs backend tests
  2. Builds the React UI (frontend/dist)
  3. Freezes Django + the UI into a folder app (PyInstaller onedir)
  4. Smoke-tests that frozen API (starts it, checks health + UI, stops it)
  5. Stages the folder into desktop/src-tauri/api-bundle (Tauri resources)
  6. Builds the NSIS Setup.exe via Tauri

On macOS/Linux it runs steps 1-2 and prints how to get a Windows build.
`--api-only` runs steps 1-5 on any OS to check the frozen API locally.

`--target win7` builds for Windows 7 instead: the API is frozen with Python
3.8 (backend/requirements-win7.txt) and the installer is the Electron 22
shell in desktop-win7/ rather than Tauri, which needs Windows 10+.

Usage:
  python scripts/buildSoftware.py
  python scripts/buildSoftware.py --skip-tests
  python scripts/buildSoftware.py --api-only
  python scripts/buildSoftware.py --target win7   (run with Python 3.8)
  scripts\\buildSoftware.bat          (Windows double-click / cmd)
  ./scripts/buildSoftware.sh          (macOS/Linux)
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


class SoftwareBuilder:
    """Orchestrate tests, UI build, API freeze, smoke test, and Tauri installer."""

    API_NAME = "mm-electricals-api"
    SMOKE_TIMEOUT_SECONDS = 120
    TARGETS = ("win10", "win7")
    # Last Python that runs on Windows 7; its DLLs are what PyInstaller bundles.
    WIN7_PYTHON = (3, 8)

    def __init__(self, *, skip_tests: bool = False, api_only: bool = False, target: str = "win10") -> None:
        self.skip_tests = skip_tests
        self.api_only = api_only
        self.target = target
        self.is_win7 = target == "win7"
        self.root = Path(__file__).resolve().parents[1]
        self.backend = self.root / "backend"
        self.frontend = self.root / "frontend"
        self.desktop = self.root / "desktop"
        self.tauri_dir = self.desktop / "src-tauri"
        self.electron_dir = self.root / "desktop-win7"
        shell_dir = self.electron_dir if self.is_win7 else self.tauri_dir
        self.api_bundle_dir = shell_dir / "api-bundle"
        self.pyinstaller_dist = self.backend / "dist"
        self.python = self._resolve_python()
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"

    @property
    def frozen_api_dir(self) -> Path:
        return self.pyinstaller_dist / self.API_NAME

    @property
    def frozen_api_exe(self) -> Path:
        return self.frozen_api_dir / (f"{self.API_NAME}.exe" if self.is_windows else self.API_NAME)

    def run(self) -> int:
        print(f"==> Shop Manager buildSoftware ({platform.system()} {platform.machine()}, target {self.target})")
        print(f"    root: {self.root}")
        print(f"    python: {self.python}")
        if self.is_win7:
            self.ensure_win7_python()
        if not self.skip_tests:
            self.run_backend_tests()
        else:
            print("==> Skipping backend tests (--skip-tests)")
        self.build_frontend()
        if not self.is_windows and not self.api_only:
            self._print_non_windows_next_steps()
            return 0
        self.ensure_pyinstaller()
        self.build_api_bundle()
        self.smoke_test_api()
        self.stage_api_bundle()
        if self.api_only:
            print(f"==> API bundle ready (--api-only): {self.frozen_api_dir}")
            return 0
        if self.is_win7:
            self.ensure_electron_tools()
            self.build_electron_installer()
        else:
            self.ensure_tauri_tools()
            self.build_tauri_installer()
        self._print_windows_outputs()
        return 0

    def _resolve_python(self) -> Path:
        """Prefer project venv, then VIRTUAL_ENV, then current interpreter (.venv-win7 first for win7)."""
        virtual_env = os.environ.get("VIRTUAL_ENV")
        venv_names = [".venv-win7"] if self.is_win7 else [".venv"]
        candidates = [
            *[self.root / name / "Scripts" / "python.exe" for name in venv_names],
            *[self.root / name / "bin" / "python" for name in venv_names],
            Path(virtual_env) / "Scripts" / "python.exe" if virtual_env else None,
            Path(virtual_env) / "bin" / "python" if virtual_env else None,
        ]
        if not self.is_win7:
            candidates += [
                Path.home() / ".virtualenvs" / "shopmanager" / "Scripts" / "python.exe",
                Path.home() / ".virtualenvs" / "shopmanager" / "bin" / "python",
            ]
        found = next(filter(lambda candidate: candidate is not None and candidate.exists(), candidates), None)
        return found or Path(sys.executable)

    def ensure_win7_python(self) -> None:
        """A newer Python links DLLs that Windows 7 does not have, so refuse to build with one."""
        probe = subprocess.run(
            [str(self.python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"],
            capture_output=True,
            text=True,
            check=False,
        )
        version = probe.stdout.strip()
        wanted = "%d.%d" % self.WIN7_PYTHON
        if version != wanted:
            raise RuntimeError(
                f"--target win7 needs Python {wanted} (found {version or 'none'} at {self.python}). "
                f"Create .venv-win7 with Python 3.8.10 and install backend/requirements-win7.txt into it."
            )
        # python.org's 3.8 for Windows ships SQLite without JSON1, which Django's JSONField needs.
        json_probe = subprocess.run(
            [str(self.python), "-c", "import sqlite3; sqlite3.connect(':memory:').execute('select json_valid(1)')"],
            capture_output=True,
            check=False,
        )
        if json_probe.returncode != 0:
            raise RuntimeError(
                f"The SQLite in {self.python} has no JSON functions (Django needs JSON_VALID). "
                f"Run: powershell -File scripts\\win7-sqlite.ps1 -Python {self.python}"
            )

    def run_backend_tests(self) -> None:
        print("==> Backend tests")
        self._run([str(self.python), "-m", "pytest", "-q"], cwd=self.backend)

    def build_frontend(self) -> None:
        print("==> Frontend production build")
        npm = self._npm()
        if not (self.frontend / "node_modules").exists():
            self._run([npm, "ci"], cwd=self.frontend)
        self._run([npm, "run", "build"], cwd=self.frontend)
        if not (self.frontend / "dist" / "index.html").is_file():
            raise RuntimeError("Frontend build did not produce frontend/dist/index.html.")

    def ensure_pyinstaller(self) -> None:
        print("==> Checking PyInstaller")
        probe = subprocess.run([str(self.python), "-m", "PyInstaller", "--version"], capture_output=True, check=False)
        if probe.returncode != 0:
            self._run([str(self.python), "-m", "pip", "install", "-q", "pyinstaller"], cwd=self.root)

    def build_api_bundle(self) -> None:
        """
        Folder build (onedir), not a single exe: starts faster, is flagged far
        less by antivirus, and has no self-extracting child process to orphan.
        """
        print("==> Freezing Django API + UI with PyInstaller (folder build)")
        entry = self.backend / "packaging" / "launch_api.py"
        work = self.backend / "build" / "pyinstaller"
        ui_data = f"{self.frontend / 'dist'}{os.pathsep}frontend_dist"
        collect_all = ["django", "rest_framework", "django_filters"]
        collect_submodules = ["apps", "config", "waitress"]
        cmd = [
            str(self.python),
            "-m",
            "PyInstaller",
            str(entry),
            "--name",
            self.API_NAME,
            "--noconfirm",
            "--clean",
            "--onedir",
            "--distpath",
            str(self.pyinstaller_dist),
            "--workpath",
            str(work),
            "--specpath",
            str(work),
            "--paths",
            str(self.backend),
            "--add-data",
            ui_data,
            "--hidden-import",
            "PIL",
            *[arg for package in collect_all for arg in ("--collect-all", package)],
            *[arg for package in collect_submodules for arg in ("--collect-submodules", package)],
        ]
        icon = self.tauri_dir / "icons" / "icon.ico"
        if self.is_windows and icon.is_file():
            cmd += ["--icon", str(icon)]
        self._run(cmd, cwd=self.backend)
        if not self.frozen_api_exe.exists():
            raise RuntimeError(f"PyInstaller finished but {self.frozen_api_exe} was not created.")
        print(f"    API folder: {self.frozen_api_dir}")

    def smoke_test_api(self) -> None:
        """Start the frozen API on a throwaway data folder and check health + UI."""
        print("==> Smoke-testing the frozen API")
        port = self._free_port()
        with tempfile.TemporaryDirectory(prefix="mm-smoke-") as data_dir:
            env = {**os.environ, "MM_PARENT_PID": str(os.getpid())}
            process = subprocess.Popen(
                [str(self.frozen_api_exe), "--port", str(port), "--data-dir", data_dir],
                cwd=str(self.frozen_api_dir),
                env=env,
            )
            try:
                health = self._wait_for_json(f"http://127.0.0.1:{port}/api/v1/health/", process)
                if health.get("status") != "ok":
                    raise RuntimeError(f"Frozen API health is not ok: {json.dumps(health)}")
                page = self._fetch(f"http://127.0.0.1:{port}/sales")
                if 'id="root"' not in page:
                    raise RuntimeError("Frozen API did not serve the React app at /sales.")
                print(f"    health ok, UI served (port {port})")
            except Exception:
                self._print_log_tail(Path(data_dir) / "logs" / "api.log")
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)

    def stage_api_bundle(self) -> None:
        """Replace the shell's api-bundle folder with the fresh PyInstaller folder."""
        print("==> Staging API folder into the desktop shell's resources")
        self.api_bundle_dir.mkdir(parents=True, exist_ok=True)
        stale = filter(lambda item: item.name != ".gitignore", self.api_bundle_dir.iterdir())
        list(map(lambda item: shutil.rmtree(item) if item.is_dir() else item.unlink(), stale))
        shutil.copytree(self.frozen_api_dir, self.api_bundle_dir, dirs_exist_ok=True)
        print(f"    staged: {self.api_bundle_dir}")

    def ensure_tauri_tools(self) -> None:
        print("==> Checking Tauri tools")
        if shutil.which("cargo") is None:
            raise RuntimeError("Rust/cargo not found. Install from https://rustup.rs then reopen the terminal.")
        npm = self._npm()
        if not (self.desktop / "node_modules").exists():
            self._run([npm, "ci"], cwd=self.desktop)

    def build_tauri_installer(self) -> None:
        print("==> Building Tauri / NSIS installer")
        self._run([self._npm(), "run", "tauri", "--", "build"], cwd=self.desktop)

    def ensure_electron_tools(self) -> None:
        print("==> Checking Electron tools")
        if not (self.electron_dir / "node_modules").exists():
            self._run([self._npm(), "ci"], cwd=self.electron_dir)

    def build_electron_installer(self) -> None:
        print("==> Building Electron 22 / NSIS installer (Windows 7)")
        self._run([self._npm(), "run", "dist"], cwd=self.electron_dir)

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _fetch(self, url: str) -> str:
        # Loopback only: bypass any system HTTP proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=5) as response:
            return response.read().decode("utf-8")

    def _wait_for_json(self, url: str, process: subprocess.Popen) -> dict:
        deadline = time.monotonic() + self.SMOKE_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Frozen API exited early with code {process.returncode}.")
            try:
                return json.loads(self._fetch(url))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Frozen API answered {exc.code} at {url}: {body[:500]}") from exc
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                time.sleep(0.5)
        raise RuntimeError(f"Frozen API did not answer {url} within {self.SMOKE_TIMEOUT_SECONDS}s.")

    def _print_log_tail(self, log: Path) -> None:
        if log.is_file():
            print(f"---- last lines of {log} ----")
            print("\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]))

    def _npm(self) -> str:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            raise RuntimeError("npm not found on PATH. Install Node.js LTS first.")
        return npm

    def _run(self, cmd: list[str], *, cwd: Path) -> None:
        print(f"    $ {' '.join(cmd)}")
        completed = subprocess.run(cmd, cwd=str(cwd), check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(cmd)}")

    def _print_non_windows_next_steps(self) -> None:
        print()
        print("==> Frontend build ready on this Mac/Linux machine.")
        print()
        print("    You cannot create a Windows .exe here.")
        print("    To get a Setup.exe you can share with Windows shops:")
        print()
        print("    1) Push this repo to GitHub")
        print('    2) Open: Actions -> "Build Windows installer" -> Run workflow')
        print("    3) Download the artifact: MM-Electricals-Windows-Setup")
        print("    4) Share that *-setup.exe with the Windows PC")
        print()
        print("    Or run on a Windows PC:")
        print("      python scripts\\buildSoftware.py")
        print()
        print("    To check the frozen API on this machine: python scripts/buildSoftware.py --api-only")

    def _print_windows_outputs(self) -> None:
        nsis = self.electron_dir / "dist" if self.is_win7 else self.tauri_dir / "target" / "release" / "bundle" / "nsis"
        print()
        print("==> Build finished.")
        list(map(lambda path: print(f"    Setup: {path}"), sorted(nsis.glob("*-setup.exe"))))
        print("    Shop data (after install) lives in %LOCALAPPDATA%\\MMElectricals\\")
        print("    Logs: %LOCALAPPDATA%\\MMElectricals\\logs\\api.log")


class BuildSoftwareCli:
    """Parse argv and run SoftwareBuilder."""

    def main(self, argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(description="Build the MM Electricals Windows software package.")
        parser.add_argument("--skip-tests", action="store_true", help="Skip pytest (faster packaging iteration).")
        parser.add_argument(
            "--api-only",
            action="store_true",
            help="Freeze + smoke-test the API on any OS without building the installer.",
        )
        parser.add_argument(
            "--target",
            choices=SoftwareBuilder.TARGETS,
            default="win10",
            help="win10: Tauri installer (Windows 10+). win7: Electron 22 installer, API frozen with Python 3.8.",
        )
        args = parser.parse_args(argv)
        try:
            return SoftwareBuilder(skip_tests=args.skip_tests, api_only=args.api_only, target=args.target).run()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(BuildSoftwareCli().main())
