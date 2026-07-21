from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import TypeAdapter

from collarai.models import RunResult

RUN_ID = re.compile(r"^[0-9a-f-]{36}$")
RUN_RESULT_ADAPTER = TypeAdapter(RunResult)


class EvidenceStore:
    """Durable per-run metadata. Screenshots and Stagehand action logs live beside it."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    def create_run(self, run_id: str) -> Path:
        path = self._run_path(run_id)
        path.mkdir(parents=True, exist_ok=False, mode=0o700)
        return path

    def save_result(self, result: RunResult) -> Path:
        path = self._run_path(result.run_id) / "result.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, path)
        path.chmod(0o600)
        return path

    def load_result(self, run_id: str) -> RunResult:
        data = json.loads((self._run_path(run_id) / "result.json").read_text(encoding="utf-8"))
        data.setdefault("operation", "screen_companies")
        return RUN_RESULT_ADAPTER.validate_python(data)

    def _run_path(self, run_id: str) -> Path:
        if not RUN_ID.fullmatch(run_id):
            raise ValueError("Invalid run ID")
        return self.root / run_id
