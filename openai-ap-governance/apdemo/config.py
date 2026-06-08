"""Environment-backed settings. No secrets in source."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env if present; real values never committed


@dataclass(frozen=True)
class Settings:
    url: str
    pat: str | None
    agent_key: str | None
    agent_uuid: str | None
    policy_id: str | None
    model: str
    openai_api_key: str | None
    owner_email: str
    version_map: dict[int, int]

    @classmethod
    def load(cls) -> "Settings":
        raw = os.getenv("TAPPASS_VERSION_MAP", "")
        version_map: dict[int, int] = {}
        if raw:
            try:
                parsed = json.loads(raw)
                version_map = {int(k): int(v) for k, v in parsed.items()}
            except Exception:
                version_map = {}
        return cls(
            url=os.getenv("TAPPASS_URL", "https://app.tappass.ai").rstrip("/"),
            pat=os.getenv("TAPPASS_PAT") or None,
            agent_key=os.getenv("TAPPASS_AGENT_KEY") or None,
            agent_uuid=os.getenv("TAPPASS_AGENT_UUID") or None,
            policy_id=os.getenv("TAPPASS_POLICY_ID") or None,
            model=os.getenv("TAPPASS_MODEL", "gpt-4o-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            owner_email=os.getenv("DEMO_OWNER_EMAIL", "demo@example.com"),
            version_map=version_map,
        )

    def require_pat(self) -> str:
        if not self.pat:
            raise SystemExit("TAPPASS_PAT is not set. Add it to .env (control-plane PAT).")
        return self.pat

    def require_agent_key(self) -> str:
        if not self.agent_key:
            raise SystemExit("TAPPASS_AGENT_KEY is not set. Run `apdemo setup` first.")
        return self.agent_key
