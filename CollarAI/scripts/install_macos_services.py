from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import time
from pathlib import Path

API_LABEL = "com.collarai.demo-api"
INFERENCE_LABEL = "com.collarai.duke-inference-tunnel"
TAILSCALE_LABEL = "com.collarai.tailscaled"
PUBLIC_ORIGIN = "https://frankyzha.github.io"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install or remove the CollarAI API, Duke tunnel, and Tailscale services"
    )
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    agents = Path.home() / "Library" / "LaunchAgents"
    support = Path.home() / "Library" / "Application Support" / "CollarAI"
    tunnel_script = support / "duke_inference_tunnel.sh"
    targets = [agents / f"{label}.plist" for label in (TAILSCALE_LABEL, INFERENCE_LABEL, API_LABEL)]
    if args.uninstall:
        for target in targets:
            _bootout(target)
            target.unlink(missing_ok=True)
        tunnel_script.unlink(missing_ok=True)
        print("Removed the CollarAI launch services. Runtime state and credentials were preserved.")
        return

    python = root / ".venv" / "bin" / "python"
    tailscaled = _executable("tailscaled", "/usr/local/opt/tailscale/bin/tailscaled")
    tailscale = _executable("tailscale", "/usr/local/bin/tailscale")
    if not python.is_file():
        raise SystemExit("Run 'uv sync --no-editable --extra dev' before installing services.")

    runtime = root / ".collarai"
    logs = runtime / "logs"
    state = runtime / "tailscale.state"
    tailscale_dir = runtime / "tailscale"
    socket = runtime / "tailscaled.sock"
    for directory in (agents, support, logs, tailscale_dir):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(root / "deploy" / "duke_inference_tunnel.sh", tunnel_script)
    tunnel_script.chmod(0o700)

    plists = {
        targets[0]: {
            "Label": TAILSCALE_LABEL,
            "ProgramArguments": [
                tailscaled,
                "--tun=userspace-networking",
                f"--state={state}",
                f"--statedir={tailscale_dir}",
                f"--socket={socket}",
            ],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 5,
            "StandardOutPath": str(logs / "tailscaled.log"),
            "StandardErrorPath": str(logs / "tailscaled.error.log"),
        },
        targets[1]: {
            "Label": INFERENCE_LABEL,
            "ProgramArguments": [
                "/bin/bash",
                str(tunnel_script),
            ],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 5,
            "StandardOutPath": str(logs / "duke-tunnel.log"),
            "StandardErrorPath": str(logs / "duke-tunnel.error.log"),
        },
        targets[2]: {
            "Label": API_LABEL,
            "ProgramArguments": [str(python), "-m", "collarai.web_api"],
            "WorkingDirectory": str(root),
            "EnvironmentVariables": {
                "COLLAR_API_REQUIRE_AUTH": "1",
                "COLLAR_API_ORIGINS": PUBLIC_ORIGIN,
                "COLLAR_API_LOG_LEVEL": "warning",
                "COLLAR_STATE_DIR": str(runtime),
                "PYTHONPATH": str(root / "src"),
            },
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 5,
            "StandardOutPath": str(logs / "api.log"),
            "StandardErrorPath": str(logs / "api.error.log"),
        },
    }

    for target, payload in plists.items():
        _bootout(target)
        with target.open("wb") as stream:
            plistlib.dump(payload, stream, sort_keys=False)
        target.chmod(0o644)
        subprocess.run(["launchctl", "bootstrap", _domain(), str(target)], check=True)

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status = subprocess.run(
            [tailscale, f"--socket={socket}", "status", "--json"],
            text=True,
            capture_output=True,
        )
        if status.returncode == 0:
            try:
                if json.loads(status.stdout).get("BackendState") == "Running":
                    break
            except json.JSONDecodeError:
                pass
        time.sleep(0.25)
    else:
        raise SystemExit(f"Tailscale did not become ready; inspect {logs}.")

    funnel = subprocess.run(
        [tailscale, f"--socket={socket}", "funnel", "--bg", "8787"],
        text=True,
        capture_output=True,
    )
    if funnel.returncode:
        raise SystemExit(
            "Services started, but Tailscale needs authentication. Run:\n"
            f"  {tailscale} --socket={socket} up\n"
            "Then rerun this installer."
        )
    print("CollarAI is running through the authenticated Tailscale Funnel.")


def _executable(name: str, fallback: str) -> str:
    resolved = shutil.which(name) or fallback
    if not Path(resolved).is_file():
        raise SystemExit(f"{name} is not installed")
    return resolved


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _bootout(plist: Path) -> None:
    if not plist.exists():
        return
    subprocess.run(
        ["launchctl", "bootout", _domain(), str(plist)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
