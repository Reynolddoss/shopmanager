"""
Start the shop inside Docker.

Docker creates the data volume as root the first time. This process starts as
root, gives that folder to the unprivileged shop user, then replaces itself
with the normal API launcher (migrations, then Waitress on port 8000).
Logs go to the container console so `docker compose logs` shows them.
"""

from __future__ import annotations

import os
import pwd
import sys
from pathlib import Path


class DockerShopEntry:
    """Hand the data volume to the shop user and start the packaged API."""

    SHOP_USER = "shop"
    DATA_DIR = Path("/data")
    PORT = "8000"

    def run(self) -> None:
        """Prepare the data folder, drop root, then become the API process."""
        self._ensure_data_dir()
        self._give_data_to_shop_user()
        self._launch_api()

    def _ensure_data_dir(self) -> None:
        """Create /data when the volume mount is empty."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _give_data_to_shop_user(self) -> None:
        """
        Let the shop user write the database, photos, and backups.

        Skipped when the process is already that user (a rebuilt image, or a
        second start where the volume was already handed over).
        """
        if os.geteuid() != 0:
            return
        account = pwd.getpwnam(self.SHOP_USER)
        # The folder itself and every file already stored in it.
        paths = [self.DATA_DIR, *self.DATA_DIR.rglob("*")]
        list(map(lambda path: os.chown(path, account.pw_uid, account.pw_gid), paths))
        os.environ["HOME"] = account.pw_dir
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)

    def _launch_api(self) -> None:
        """Replace this process with packaging/launch_api.py. There is no parent to watch."""
        launcher = Path(__file__).resolve().parent / "launch_api.py"
        os.execv(
            sys.executable,
            [
                sys.executable,
                str(launcher),
                "--host",
                "0.0.0.0",
                "--port",
                self.PORT,
                "--data-dir",
                str(self.DATA_DIR),
                "--console",
            ],
        )


class DockerEntryMain:
    """Process entry used by the image CMD."""

    @staticmethod
    def main() -> None:
        DockerShopEntry().run()


if __name__ == "__main__":
    DockerEntryMain.main()
