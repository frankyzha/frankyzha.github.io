from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    state_dir: Path
    headless: bool = True
    browser_timeout_ms: int = 15_000
    toy_base_url: str = "http://127.0.0.1:8765"
    toy_username: str = "demo@collarai.local"
    toy_password: str = "demo"
    pitchbook_url: str = "https://my.pitchbook.com"
    pitchbook_cdp_url: str = "http://127.0.0.1:9223"
    stagehand_model: str = "openai/gemma-4-26b-a4b-it"
    stagehand_model_base_url: str = "http://127.0.0.1:8000/v1"
    stagehand_model_api_key: str = "local"

    @property
    def profile_dir(self) -> Path:
        return self.state_dir / "profiles"

    @property
    def evidence_dir(self) -> Path:
        return self.state_dir / "runs"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            state_dir=Path(os.getenv("COLLAR_STATE_DIR", ".collarai")).resolve(),
            headless=_env_bool("COLLAR_HEADLESS", True),
            browser_timeout_ms=int(os.getenv("COLLAR_BROWSER_TIMEOUT_MS", "15000")),
            toy_base_url=os.getenv("COLLAR_TOY_URL", "http://127.0.0.1:8765").rstrip("/"),
            toy_username=os.getenv("COLLAR_TOY_USERNAME", "demo@collarai.local"),
            toy_password=os.getenv("COLLAR_TOY_PASSWORD", "demo"),
            pitchbook_url=os.getenv("COLLAR_PITCHBOOK_URL", "https://my.pitchbook.com").rstrip("/"),
            pitchbook_cdp_url=os.getenv("COLLAR_PITCHBOOK_CDP_URL", "http://127.0.0.1:9223").rstrip(
                "/"
            ),
            stagehand_model=os.getenv("COLLAR_STAGEHAND_MODEL", "openai/gemma-4-26b-a4b-it"),
            stagehand_model_base_url=os.getenv(
                "COLLAR_STAGEHAND_MODEL_BASE_URL", "http://127.0.0.1:8000/v1"
            ).rstrip("/"),
            stagehand_model_api_key=os.getenv("COLLAR_STAGEHAND_MODEL_API_KEY", "local"),
        )


def profile_path(settings: Settings, session_key: str) -> Path:
    profile_hash = hashlib.sha256(session_key.encode()).hexdigest()[:16]
    return settings.profile_dir / profile_hash
