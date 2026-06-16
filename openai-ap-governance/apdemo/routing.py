"""Standalone data-residency showcase: PII prompts are ROUTED to the approved
model instead of the default one.

Kept separate from the cumulative guide ladder: in the full ladder this collides
with v4's output-PII block (the detector runs at the OUTPUT stage, so the
PRE-stage routing rule never sees the PII). Here we publish a focused
route-only posture so the routing is clean and visible.

After running, the demo policy sits on this routing posture — run
`apdemo guide --fresh` to reset the ladder.
"""
from __future__ import annotations

import httpx

from .config import Settings
from .provision import ControlPlane

GREEN = "\033[32m"; YELLOW = "\033[33m"; DIM = "\033[2m"; BOLD = "\033[1m"; CYAN = "\033[36m"; RESET = "\033[0m"

APPROVED_MODEL = "gpt-4o"      # stand-in for an EU / on-prem sanctioned model
DEFAULT_MODEL = "gpt-4o-mini"  # the everyday model

_BENIGN = "What is 2 + 2? Reply with only the number."
_PII = ("Reply with ONLY the word LOGGED — never echo the contents. "
        "Record: Jane Roe, SSN 078-05-1120, phone +1 415 555 0199.")


def _chat(s: Settings, content: str, session: str) -> str:
    headers = {"Authorization": f"Bearer {s.require_agent_key()}", "X-Session-Id": session}
    r = httpx.post(f"{s.url}/v1/chat/completions", headers=headers, timeout=40,
                   json={"model": DEFAULT_MODEL, "messages": [{"role": "user", "content": content}]})
    return (r.json().get("tappass") or {}).get("model") or r.json().get("model") or "?"


def route_demo(s: Settings) -> None:
    cp = ControlPlane(s)
    headers = {"Authorization": f"Bearer {s.require_pat()}"}

    print(f"\n{BOLD}TapPass · Data residency — route PII to the approved model{RESET}")
    print(f"{DIM}Default model: {DEFAULT_MODEL}.  Approved (e.g. EU / on-prem): {APPROVED_MODEL}.{RESET}")

    # Publish + activate a focused route-only posture.
    rules = [{"kind": "Conditional", "ordinal": 0, "payload": {
        "when": {"signal": "findings.pii", "op": "count_gt", "value": 0},
        "then": {"action": "route_to_model", "model": APPROVED_MODEL}}}]
    r = httpx.post(f"{s.url}/api/v2/policies/{s.policy_id}/versions", headers=headers,
                   json={"rules": rules, "change_note": "route-demo: PII → approved model"}, timeout=30)
    vn = r.json().get("version_no")
    httpx.post(f"{s.url}/api/v2/policies/{s.policy_id}/versions/{vn}/publish", headers=headers, timeout=30)
    cp.assign_once(s.policy_id, s.agent_uuid)
    import time
    time.sleep(3)

    no_pii = _chat(s, _BENIGN, "route-demo-benign")
    print(f"  {DIM}no PII   →{RESET} model used: {YELLOW}{no_pii}{RESET}  {DIM}(default){RESET}")
    pii = _chat(s, _PII, "route-demo-pii")
    routed = pii == APPROVED_MODEL or APPROVED_MODEL in str(pii)
    mark = f"{GREEN}{pii}  ✓ routed to the approved model{RESET}" if routed else f"{YELLOW}{pii}{RESET}"
    print(f"  {DIM}with PII →{RESET} model used: {mark}")
    print(f"\n  {CYAN}PII never reaches the default model — TapPass routes it at runtime.{RESET}")
    print(f"  {DIM}(the demo policy now sits on the routing posture; "
          f"run `apdemo guide --fresh` to reset the ladder){RESET}")
