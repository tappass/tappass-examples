"""PAT-driven control-plane client + pure request-body builders.

Endpoints (verified live against app.tappass.ai):
  GET  /api/me                                          -> {org_id (home slug), ...}
  POST /api/agents/onboard   (omit org_id!)             -> {agent_uuid, org_id, api_key:{api_key}}
  POST /api/agents/{uuid}/developer-keys                -> {api_key} (re-mint a data-plane key)
  GET  /api/agents                                      -> {data:[{agent_uuid, agent_id, org_id}]}
  POST /api/v2/policies                                 -> {id}
  POST /api/v2/policies/{id}/versions                   -> {version_no, status:"draft"}
  POST /api/v2/policies/{id}/versions/{v}/publish       -> active (retires prior)
  POST /api/v2/policies/{id}/assignments                -> pins the CURRENTLY-ACTIVE version

Governance lifecycle facts that shape this client:
  * A policy allows only ONE open draft at a time (ADR 0014). You cannot stage
    all six versions up front — you publish the draft before creating the next.
  * A retired version cannot be re-activated (pull-back only reverts an *active*
    version to draft). The active version moves FORWARD only.
  * Assignment pins whatever version is active at assign-time.
  => `activate(n)` creates vN's rules as a fresh draft, publishes it (becoming the
     new active version, retiring the prior), and assigns — one atomic forward step.
     This needs no persisted version_map: it uses the version_no the server returns.
"""
from __future__ import annotations

import httpx

from .config import Settings
from .rules import change_note, rules_for_version


# ── pure body builders (unit-tested) ─────────────────────────────
def onboard_body(*, agent_id: str, owner_email: str) -> dict:
    # org_id is intentionally OMITTED so the server resolves the caller's
    # resource org from the PAT. (The PAT identity's home org from /api/me can
    # differ from the org it provisions into; passing the wrong one => 403.)
    return {
        "agent_id": agent_id,
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

    def _find_agent(self, agent_id: str) -> dict | None:
        for a in self._get("/api/agents").get("data", []):
            if a.get("agent_id") == agent_id:
                return a
        return None

    def _mint_key(self, agent_uuid: str) -> str:
        resp = self._post(
            f"/api/agents/{agent_uuid}/developer-keys",
            {"developer_email": self.s.owner_email, "name": "ap-demo",
             "expires_days": 120})
        return resp["api_key"]

    # — agent (idempotent) —
    def onboard_agent(self, agent_id: str) -> dict:
        """Create the agent, or reuse it if it already exists (re-minting a key).

        Returns {agent_uuid, agent_key, org_id}. The server-assigned org_id is
        the authoritative resource org (can differ from /api/me's home org).
        """
        existing = self._find_agent(agent_id)
        if existing:
            uuid = existing["agent_uuid"]
            return {"agent_uuid": uuid, "agent_key": self._mint_key(uuid),
                    "org_id": existing["org_id"]}
        resp = self._post("/api/agents/onboard", onboard_body(
            agent_id=agent_id, owner_email=self.s.owner_email))
        return {"agent_uuid": resp["agent_uuid"],
                "agent_key": resp["api_key"]["api_key"],
                "org_id": resp["org_id"]}

    # — policy —
    def create_policy(self, name: str, org_id: str) -> tuple[str, str]:
        """Create a policy; on a unique-name conflict, suffix until it lands.

        Policies can't be deleted via the API, so re-running setup would collide
        on the name — we walk "<name>", "<name> (2)", … until one is accepted.
        Returns (policy_id, final_name).
        """
        attempt = 0
        while True:
            candidate = name if attempt == 0 else f"{name} ({attempt + 1})"
            r = self._http.post("/api/v2/policies",
                                json=policy_body(org_id=org_id, name=candidate))
            if r.status_code < 400:
                return r.json()["id"], candidate
            if r.status_code == 409 and attempt < 50:
                attempt += 1
                continue
            raise SystemExit(f"POST /api/v2/policies -> {r.status_code}: {r.text}")

    def create_version(self, policy_id: str, n: int) -> int:
        resp = self._post(f"/api/v2/policies/{policy_id}/versions", version_body(n))
        return resp["version_no"]

    def publish(self, policy_id: str, version_no: int) -> dict:
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/publish")

    def assign(self, policy_id: str, agent_uuid: str) -> dict:
        return self._post(f"/api/v2/policies/{policy_id}/assignments",
                          assignment_body(agent_uuid=agent_uuid))

    def activate(self, policy_id: str, n: int, agent_uuid: str) -> int:
        """One forward step: create version N's rules as a fresh draft, publish
        it (new active version, retiring the prior), and assign to the agent so
        the assignment pins this version. Returns the server version_no.
        """
        version_no = self.create_version(policy_id, n)
        self.publish(policy_id, version_no)
        self.assign(policy_id, agent_uuid)
        return version_no

    def pull_back(self, policy_id: str, version_no: int) -> dict:
        """Revert an ACTIVE version back to draft (so it stops governing)."""
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/pull-back")

    def active_version_no(self, policy_id: str) -> int | None:
        for v in self._get(f"/api/v2/policies/{policy_id}/versions").get("data", []):
            if v.get("status") == "active":
                return v.get("version_no")
        return None

    def agent_org(self, agent_id: str) -> str | None:
        rec = self._find_agent(agent_id)
        return rec.get("org_id") if rec else None

    def neutralize(self, policy_id: str) -> None:
        """Stop a policy from governing the agent: pull its active version back to
        draft so its (still-present) assignment no longer composes. Used when
        switching to a fresh policy so the old one doesn't stack on top."""
        n = self.active_version_no(policy_id)
        if n is not None:
            try:
                self.pull_back(policy_id, n)
            except SystemExit:
                pass  # already draft / nothing to pull back — fine


def setup(settings: Settings, agent_id: str = "ap-demo-agent",
          policy_name: str = "AP Demo Policy") -> dict:
    """Create (or reuse) the demo agent and a fresh empty policy.

    Versions are NOT staged here — the one-open-draft + forward-only lifecycle
    means each posture is created+published+assigned on demand by `activate(n)`.

    Returns values to persist to .env: {agent_uuid, agent_key, org_id, policy_id}.
    """
    cp = ControlPlane(settings)
    agent = cp.onboard_agent(agent_id)
    policy_id, policy_name_final = cp.create_policy(
        policy_name, org_id=agent["org_id"])
    return {"agent_uuid": agent["agent_uuid"], "agent_key": agent["agent_key"],
            "org_id": agent["org_id"], "policy_id": policy_id,
            "policy_name": policy_name_final}
