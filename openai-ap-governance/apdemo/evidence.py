"""Compliance evidence — the governed-decision audit as an exportable report.

Collibra's language: every agent action that governance touched, with the
verdict, the rule that fired, and (for approvals) who signed off and when —
the audit-grade evidence a data-governance team needs. `apdemo evidence`
prints it and writes evidence.json; the guided demo ends on it.

The control mapping is illustrative (EU AI Act Article 14 — human oversight;
GDPR Article 5 — integrity/confidentiality) to show how each decision lines up
with a compliance framework.
"""
from __future__ import annotations

import json
import os

import httpx

from .config import Settings

GREEN = "\033[32m"; RED = "\033[31m"; YELLOW = "\033[33m"; DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"

#: Illustrative control mapping per decision kind.
_CONTROL = {
    "blocked": "EU AI Act Art. 14 (human oversight) · GDPR Art. 5 (integrity)",
    "approved": "EU AI Act Art. 14 (human-in-the-loop) — steward sign-off recorded",
    "allowed": "Observed + audited (least-privilege baseline)",
}


def collect(s: Settings, *, interval: str = "24h", limit: int = 300) -> list[dict]:
    """Governed decisions for the demo agent, newest first, as evidence rows."""
    headers = {"Authorization": f"Bearer {s.require_pat()}"}
    r = httpx.get(f"{s.url}/api/audit", headers=headers, timeout=30,
                  params={"agent_id": s.agent_id, "interval": interval, "limit": limit})
    if r.status_code >= 400:
        raise SystemExit(f"audit query failed: HTTP {r.status_code} {r.text[:160]}")
    rows: list[dict] = []
    for ev in r.json().get("data", []):
        et = ev.get("event_type")
        if et not in ("govern_allow", "govern_block"):
            continue
        d = ev.get("details", {}) or {}
        ap = d.get("approval") or {}
        decision = ("blocked" if et == "govern_block"
                    else "approved" if ap.get("decided_by") else "allowed")
        rows.append({
            "when": ev.get("timestamp"),
            "agent": ev.get("agent_id"),
            "action": ev.get("resource") or (d.get("tool") or "—"),
            "decision": decision,
            "rule": d.get("reason") or ev.get("matched_rule") or d.get("matched_rule") or "",
            "approved_by": str(ap.get("decided_by")) if ap.get("decided_by") else None,
            "approved_at": ap.get("decided_at"),
            "session_id": ev.get("session_id"),
            "control": _CONTROL[decision],
        })
    return rows


def report(s: Settings, *, write: bool = True) -> list[dict]:
    """Print the evidence report and (optionally) write evidence.json."""
    rows = collect(s)
    n_block = sum(r["decision"] == "blocked" for r in rows)
    n_appr = sum(r["decision"] == "approved" for r in rows)
    n_allow = sum(r["decision"] == "allowed" for r in rows)

    print(f"\n{BOLD}TapPass · Governance evidence — agent {s.agent_id}{RESET}")
    print(f"{DIM}Every governed action, with the rule that fired and the human who "
          f"signed off. Audit-grade, exportable.{RESET}")
    print(f"{DIM}{'─'*92}{RESET}")
    print(f"  {BOLD}{'when':<20}{'action':<26}{'decision':<11}{'who approved':<14}rule{RESET}")
    for r in rows[:40]:
        when = (r["when"] or "")[:19].replace("T", " ")
        dec = r["decision"]
        color = RED if dec == "blocked" else YELLOW if dec == "approved" else GREEN
        who = (r["approved_by"] or "")[:12]
        print(f"  {when:<20}{r['action'][:25]:<26}{color}{dec:<11}{RESET}{who:<14}"
              f"{DIM}{r['rule'][:34]}{RESET}")
    print(f"{DIM}{'─'*92}{RESET}")
    print(f"  {RED}{n_block} blocked{RESET} · {YELLOW}{n_appr} approved (steward sign-off){RESET} "
          f"· {GREEN}{n_allow} allowed{RESET}   — mapped to EU AI Act Art. 14 / GDPR Art. 5")

    if write:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evidence.json")
        payload = {"agent_id": s.agent_id, "summary": {"blocked": n_block,
                   "approved": n_appr, "allowed": n_allow}, "decisions": rows}
        try:
            with open(path, "w") as fh:
                json.dump(payload, fh, indent=2, default=str)
            print(f"  {DIM}→ exported {len(rows)} decisions to {path}{RESET}")
        except OSError:
            pass
    return rows
