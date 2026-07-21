from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlparse

from collarai.config import Settings, profile_path


class ChromeSession:
    """Own a normal Chrome process that Stagehand may attach to over local CDP."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        parsed = urlparse(settings.pitchbook_cdp_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("PitchBook CDP must use a local HTTP endpoint")
        self.port = parsed.port or 9223

    @property
    def profile(self) -> Path:
        return profile_path(self.settings, "pitchbook")

    def ensure_running(self, url: str) -> bool:
        """Start Chrome when needed. Return True only when a new process was started."""
        if self.is_running():
            return False
        self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.profile.chmod(0o700)
        subprocess.Popen(
            [
                self._executable(),
                f"--user-data-dir={self.profile}",
                f"--remote-debugging-port={self.port}",
                "--remote-debugging-address=127.0.0.1",
                "--no-first-run",
                "--no-default-browser-check",
                url,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.is_running():
                return True
            time.sleep(0.1)
        raise RuntimeError("Chrome started but its local debugging endpoint did not become ready")

    def is_running(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.settings.pitchbook_cdp_url}/json/version", timeout=0.5
            ) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            return False

    def open_url(self, url: str) -> None:
        request = urllib.request.Request(
            f"{self.settings.pitchbook_cdp_url}/json/new?{quote(url, safe='')}",
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=5):
            return

    @staticmethod
    def _executable() -> str:
        candidates = (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta"),
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/chromium"),
        )
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        for command in ("google-chrome", "google-chrome-stable", "chromium"):
            if executable := shutil.which(command):
                return executable
        raise RuntimeError("Google Chrome was not found")
