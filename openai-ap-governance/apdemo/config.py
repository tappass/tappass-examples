"""Environment-backed settings. No secrets in source."""
from __future__ import annotations

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
    agent_id: str
    policy_id: str | None
    # Org SLUG (e.g. "collibra-ba9ed2") for control-plane policy ops. The agent
    # record reports the org as a UUID, but /api/v2/policies' cross-org check
    # requires the slug — they must match the tenant, so carry it explicitly.
    org: str | None
    model: str
    openai_api_key: str | None
    owner_email: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            url=os.getenv("TAPPASS_URL", "https://app.tappass.ai").rstrip("/"),
            pat=os.getenv("TAPPASS_PAT") or None,
            agent_key=os.getenv("TAPPASS_AGENT_KEY") or None,
            agent_uuid=os.getenv("TAPPASS_AGENT_UUID") or None,
            agent_id=os.getenv("TAPPASS_AGENT_ID", "ap-demo-agent"),
            policy_id=os.getenv("TAPPASS_POLICY_ID") or None,
            org=os.getenv("TAPPASS_ORG") or None,
            model=os.getenv("TAPPASS_MODEL", "gpt-4o-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            owner_email=os.getenv("DEMO_OWNER_EMAIL", "demo@example.com"),
        )

    def require_pat(self) -> str:
        if not self.pat:
            raise SystemExit("TAPPASS_PAT is not set. Add it to .env (control-plane PAT).")
        return self.pat

    def require_agent_key(self) -> str:
        if not self.agent_key:
            raise SystemExit("TAPPASS_AGENT_KEY is not set. Run `apdemo setup` first.")
        return self.agent_key
