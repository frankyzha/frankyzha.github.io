from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from collarai.credentials import InferenceTokenStore

LOGIN = "yz1075@login.cs.duke.edu"
REMOTE_ROOT = "/usr/project/xtmp/yz1075/CollarAI"
JOB_NAME = "collarai-gemma"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision the authenticated Duke Gemma worker without printing its token"
    )
    parser.add_argument("--rotate-token", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    token = InferenceTokenStore().create(rotate=args.rotate_token)
    _run(
        [
            "ssh",
            LOGIN,
            f"umask 077; mkdir -p {REMOTE_ROOT}/.secrets {REMOTE_ROOT}/logs; "
            f"tee {REMOTE_ROOT}/.secrets/llama-api-keys >/dev/null",
        ],
        input=f"{token}\n",
    )
    _run(
        [
            "scp",
            str(root / "deploy" / "duke_gemma_server.sbatch"),
            f"{LOGIN}:{REMOTE_ROOT}/duke_gemma_server.sbatch",
        ]
    )

    jobs = _output(
        [
            "ssh",
            LOGIN,
            f"squeue -h -u yz1075 --name={JOB_NAME} -o '%A %T %N'",
        ]
    ).strip()
    if jobs and not args.rotate_token:
        print(f"Duke inference job already active: {jobs}")
        return
    if jobs:
        job_ids = [line.split()[0] for line in jobs.splitlines()]
        _run(["ssh", LOGIN, "scancel", *job_ids])

    job_id = _output(
        [
            "ssh",
            LOGIN,
            f"chmod 700 {REMOTE_ROOT}/duke_gemma_server.sbatch; "
            f"sbatch --parsable {REMOTE_ROOT}/duke_gemma_server.sbatch",
        ]
    ).strip()
    print(f"Submitted Duke inference job {job_id}. The token remains in protected stores.")


def _run(command: list[str], *, input: str | None = None) -> None:
    subprocess.run(command, check=True, text=True, input=input)


def _output(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    ).stdout


if __name__ == "__main__":
    main()
