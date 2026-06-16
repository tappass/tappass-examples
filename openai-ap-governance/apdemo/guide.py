"""Interactive guided demo — press ENTER to walk the v0→v6 ladder.

Each step: shows the narration, what changes in TapPass (+ the dashboard URL),
waits for you to press ENTER, applies the governance change, runs the agent, and
links the governed trace. Designed so you can just hit ENTER through the story
with the dashboard open alongside.
"""
from __future__ import annotations

import sys

import httpx

from . import agent as agent_mod
from .config import Settings
from .provision import ControlPlane, _writeback_env
from .rules import change_note
from .scenarios import V2_REDACT_PROMPT, prompt_for

BOLD = "\033[1m"; DIM = "\033[2m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
CYAN = "\033[36m"; RESET = "\033[0m"
RULE = "─" * 72

STEPS = [
    {"version": 0, "title": "v0 — the agent you sent us (ungoverned)",
     "why": "Your LangGraph agent with cowsay + calculator, talking STRAIGHT to "
            "OpenAI — no TapPass.",
     "scenario": "happy",
     "watch": "Open the dashboard: nothing. No audit, no cost, no control."},
    {"version": 1, "title": "v1 — two lines, now observed",
     "why": "base_url → the TapPass gateway, and tappass.govern() around the "
            "tools. Nothing else in the agent changes.",
     "scenario": "happy",
     "watch": "Same answer — now a governed turn with a full trace (cost, latency)."},
    {"version": 2, "title": "v2 — govern the cow's words",
     "why": "Policy blocks a banned name in the message, and redacts an internal "
            "reference code out of it.",
     "scenario": "governed",
     "extra_prompt": V2_REDACT_PROMPT,
     "watch": "'voldemort' → blocked; then a second run scrubs 'ACME-4471' but "
              "still lets the cow speak."},
    {"version": 3, "title": "v3 — rate-limit the tool",
     "why": "cowsay is capped at 3 calls per 2 minutes, counted from the audit trail.",
     "scenario": "governed",
     "watch": "The 4th cowsay in the run is blocked — rate_limited."},
    {"version": 4, "title": "v4 — stop data leaving",
     "why": "PII / secrets are blocked in the agent's output.",
     "scenario": "governed",
     "watch": "Reading out a vendor's bank number → blocked (pii_in_output)."},
    {"version": 5, "title": "v5 — gate the dangerous action",
     "why": "The payment write tool is blocked outright.",
     "scenario": "governed",
     "watch": "The agent tries to schedule a payment → blocked."},
    {"version": 6, "title": "v6 — human in the loop",
     "why": "Payments are allowed, but each one needs human approval.",
     "scenario": "governed",
     "watch": "The agent halts for sign-off — approve it (ENTER) and it resumes; "
              "the approval + execution are audited."},
    {"version": 7, "title": "v7 — context-aware (the fraud beat)",
     "why": "Small payments flow; large ones AND vendor bank-account changes need "
            "elevated approval.",
     "scenario": "governed",
     "watch": "A €25k payment halts for sign-off — approve it (ENTER) to resume."},
    {"version": 8, "title": "v8 — govern the agent that touches your catalog",
     "why": "The same kernel now governs an agent editing your Collibra-style "
            "data catalog.",
     "scenario": "governed",
     "watch": "The agent tries to WEAKEN a data classification → blocked."},
]


def _pause(prompt: str = "  ↵  press ENTER to continue") -> None:
    try:
        input(f"{DIM}{prompt}{RESET}")
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def _approve(s: Settings, name: str, args: dict, detail: dict) -> bool:
    """Human-in-the-loop sign-off, invoked when TapPass holds a tool call.

    You are the reviewer TapPass routed the request to. The agent's govern call
    returned `needs_approval` and persisted a real pending request; the SDK hands
    us its `request_id`. On ENTER we decide it as the operator
    (POST /v1/me/approvals/{id}/decide, control-plane PAT) with scope=ALWAYS — a
    standing grant, so one sign-off covers the agent's whole retry loop for this
    turn (no re-ask). The kernel's ApprovalProducer reads the decision as a fact
    on re-submit and governance re-allows; the trace records who approved + when.
    Ctrl-C denies. If no request_id is present (older server / no operator in the
    agent's org), we fall back to the fingerprint grant (POST /v1/govern/approve).
    """
    tier = str(detail.get("tier", "authenticated")).upper()
    reason = detail.get("reason", "approval required")
    request_id = detail.get("request_id") or ""
    arg_str = ", ".join(f"{k}={v}" for k, v in args.items())
    print(f"\n  {YELLOW}⏸  {tier} APPROVAL REQUIRED{RESET}")
    print(f"     {name}({arg_str})")
    print(f"     {DIM}{reason}{RESET}")
    try:
        input(f"  {YELLOW}↵  press ENTER to approve as reviewer{RESET}"
              f"{DIM}  (Ctrl-C to deny){RESET}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {DIM}✗ denied — the action stays blocked.{RESET}")
        return False
    headers = {"Authorization": f"Bearer {s.require_pat()}"}
    try:
        if request_id:
            r = httpx.post(
                f"{s.url}/v1/me/approvals/{request_id}/decide",
                headers=headers,
                json={"decision": "approve", "scope": "always"},
                timeout=15,
            )
            where = f"decided request {request_id[:8]} (scope=always)"
        else:
            # Fallback: no persisted request to decide — grant by fingerprint.
            r = httpx.post(
                f"{s.url}/v1/govern/approve",
                headers=headers,
                json={"agent_id": s.agent_id, "tool": name, "args": args,
                      "scope": "always"},
                timeout=15,
            )
            where = "granted by fingerprint (scope=always)"
        if r.status_code >= 400:
            print(f"  {DIM}✗ approve failed: HTTP {r.status_code} {r.text[:140]}{RESET}")
            return False
    except Exception as e:
        print(f"  {DIM}✗ approve error: {type(e).__name__}: {e}{RESET}")
        return False
    print(f"  {GREEN}✓ approved — {where}; governance re-allows on resubmit{RESET}")
    return True


def run_guide(s: Settings, fresh: bool = False) -> None:
    if not s.policy_id or not s.agent_uuid:
        raise SystemExit("Run `apdemo setup` and fill .env first.")
    cp = ControlPlane(s)

    policy_id = s.policy_id
    if fresh:
        # Re-runnable from a pristine starting point: neutralise the current
        # policy (so its assignment stops governing the agent), then mint a
        # brand-new policy whose version history starts clean at v1.
        print(f"{DIM}Resetting to a fresh policy…{RESET}")
        cp.neutralize(s.policy_id)
        # Policy ops need the org SLUG (TAPPASS_ORG); the agent reports a UUID.
        org = s.org or cp.agent_org(s.agent_id) or ""
        policy_id, policy_name = cp.create_policy("AP Demo Policy", org_id=org)
        # Persist the fresh policy so later runs REUSE it (clean + no new bloat).
        _writeback_env({"TAPPASS_POLICY_ID": policy_id})
        print(f"{GREEN}✓ fresh policy '{policy_name}' ({policy_id}){RESET}")

    policy_url = f"{s.url}/app/policies/{policy_id}"
    agent_url = f"{s.url}/app/agents/{s.agent_uuid}"

    print(f"\n{BOLD}TapPass · Accounts-Payable agent governance demo{RESET}")
    print(f"{DIM}Agent:  {agent_url}{RESET}")
    print(f"{DIM}Policy: {policy_url}{RESET}")
    print(f"{DIM}Press ENTER through v0→v8. Keep the dashboard open alongside.{RESET}")
    _pause("  ↵  press ENTER to begin")

    for step in STEPS:
        v = step["version"]
        prompt = prompt_for(v, step["scenario"])
        print(f"\n{CYAN}{RULE}{RESET}")
        print(f"{BOLD}{step['title']}{RESET}")
        print(f"  {step['why']}")
        if v >= 1:
            print(f"\n  {YELLOW}▶ TapPass change:{RESET} activate policy "
                  f"{BOLD}v{v}{RESET} — {change_note(v)}")
            print(f"    {DIM}{policy_url}{RESET}")
        else:
            print(f"\n  {DIM}(not routed through TapPass — the ungoverned baseline){RESET}")
        print(f"\n  {DIM}Prompt:{RESET}    \"{prompt}\"")
        print(f"  {DIM}Watch for:{RESET} {step['watch']}")
        _pause()

        if v >= 1:
            version_no = cp.activate(policy_id, v, s.agent_uuid)
            print(f"  {GREEN}✓ policy v{v} is now active "
                  f"(version {version_no}) and assigned{RESET}")

        print()
        sid = agent_mod.run(
            v, prompt, s,
            approve_cb=lambda n, a, d: _approve(s, n, a, d))
        if v >= 1 and sid:
            print(f"\n  {CYAN}→ open the governed trace:{RESET} "
                  f"{s.url}/app/sessions/{sid}")
        # Some steps show a second beat on the same posture (e.g. v2's redact
        # flourish: a different message the policy scrubs rather than blocks).
        extra = step.get("extra_prompt")
        if extra:
            print(f"\n  {DIM}…and again, redacted:{RESET} \"{extra}\"")
            _pause("  ↵  press ENTER to run the redact beat")
            agent_mod.run(v, extra, s,
                          approve_cb=lambda n, a, d: _approve(s, n, a, d))
        _pause("  ↵  press ENTER for the next step")

    print(f"\n{CYAN}{RULE}{RESET}")
    print(f"{BOLD}That's the ladder.{RESET} Eight policy versions, activated live — "
          "and the agent code never changed.")
    print(f"  Policy version history: {policy_url}")
    if fresh and policy_id != s.policy_id:
        print(f"\n  {DIM}This run used a fresh policy. To keep it as the default,"
              f" set in .env:{RESET}\n  TAPPASS_POLICY_ID={policy_id}")
    print()
