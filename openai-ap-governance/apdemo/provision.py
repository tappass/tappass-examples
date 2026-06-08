"""PAT-driven control-plane client + pure request-body builders.

Endpoints verified against core repo:
  GET  /api/me                                          -> {org_id (slug), ...}
  POST /api/agents/onboard                              -> {agent_uuid, api_key:{api_key}}
  POST /api/v2/policies                                 -> {id}
  POST /api/v2/policies/{id}/versions                   -> {version_no}
  POST /api/v2/policies/{id}/versions/{v}/publish
  POST /api/v2/policies/{id}/versions/{v}/pull-back
  POST /api/v2/policies/{id}/assignments
"""
from __future__ import annotations

import httpx

from .config import Settings
from .rules import change_note, rules_for_version


# ── pure body builders (unit-tested) ─────────────────────────────
def onboard_body(*, agent_id: str, org_id: str, owner_email: str) -> dict:
    return {
        "agent_id": agent_id,
        "org_id": org_id,
        "owner_email": owner_email,
        "description": "Incremental AP-agent governance demo",
        "framework": "custom",
        "intended_use": "Accounts Payable assistant (demo)",
    }


def policy_body(*, org_id: str, name: str) -> dict:
    return {"org_id": org_id, "name": name,
            "description": "Incremental AP-agent governance demo"}


def version_body(n: int) -> dict:
    return {"rules": rules_for_version(n), "change_note": change_note(n)}


def assignment_body(*, agent_uuid: str) -> dict:
    return {"scope_type": "agent", "scope_id": agent_uuid}


# ── HTTP client ──────────────────────────────────────────────────
class ControlPlane:
    def __init__(self, settings: Settings):
        self.s = settings
        self._http = httpx.Client(
            base_url=settings.url,
            headers={"Authorization": f"Bearer {settings.require_pat()}"},
            timeout=30,
        )

    def _post(self, path: str, body: dict | None = None) -> dict:
        r = self._http.post(path, json=body or {})
        if r.status_code >= 400:
            raise SystemExit(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content else {}

    def _get(self, path: str) -> dict:
        r = self._http.get(path)
        if r.status_code >= 400:
            raise SystemExit(f"GET {path} -> {r.status_code}: {r.text}")
        return r.json()

    # — org —
    def org_slug(self) -> str:
        return self._get("/api/me")["org_id"]

    # — agent —
    def onboard_agent(self, agent_id: str) -> dict:
        org = self.org_slug()
        resp = self._post("/api/agents/onboard", onboard_body(
            agent_id=agent_id, org_id=org, owner_email=self.s.owner_email))
        return {"agent_uuid": resp["agent_uuid"],
                "agent_key": resp["api_key"]["api_key"]}

    # — policy —
    def create_policy(self, name: str) -> str:
        org = self.org_slug()
        return self._post("/api/v2/policies", policy_body(org_id=org, name=name))["id"]

    def create_version(self, policy_id: str, n: int) -> int:
        resp = self._post(f"/api/v2/policies/{policy_id}/versions", version_body(n))
        return resp["version_no"]

    def publish(self, policy_id: str, version_no: int) -> dict:
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/publish")

    def pull_back(self, policy_id: str, version_no: int) -> dict:
        """Re-activate a previously-superseded version (used when re-running the demo or stepping backward)."""
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/pull-back")

    def assign(self, policy_id: str, agent_uuid: str) -> dict:
        return self._post(f"/api/v2/policies/{policy_id}/assignments",
                          assignment_body(agent_uuid=agent_uuid))


def setup(settings: Settings, agent_id: str = "ap-demo-agent",
          policy_name: str = "AP Demo Policy") -> dict:
    """Create the agent + one policy with six draft versions (1..6).

    Returns the values the caller must persist to .env:
    {agent_uuid, agent_key, policy_id, version_map}.
    """
    cp = ControlPlane(settings)
    agent = cp.onboard_agent(agent_id)
    policy_id = cp.create_policy(policy_name)
    version_map = {n: cp.create_version(policy_id, n) for n in range(1, 7)}
    return {"agent_uuid": agent["agent_uuid"], "agent_key": agent["agent_key"],
            "policy_id": policy_id, "version_map": version_map}
