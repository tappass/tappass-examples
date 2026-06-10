"""Interactive guided demo — press ENTER to walk the v0→v6 ladder.

Each step: shows the narration, what changes in TapPass (+ the dashboard URL),
waits for you to press ENTER, applies the governance change, runs the agent, and
links the governed trace. Designed so you can just hit ENTER through the story
with the dashboard open alongside.
"""
from __future__ import annotations

import sys

from . import agent as agent_mod
from .config import Settings
from .provision import ControlPlane
from .rules import change_note
from .scenarios import prompt_for

BOLD = "\033[1m"; DIM = "\033[2m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
CYAN = "\033[36m"; RESET = "\033[0m"
RULE = "─" * 72

STEPS = [
    {"version": 0, "title": "v0 — the agent you have today (ungoverned)",
     "why": "A plain OpenAI agent. The call goes STRAIGHT to OpenAI — no TapPass.",
     "scenario": "happy",
     "watch": "Open the dashboard: nothing. No audit, no cost, no control."},
    {"version": 1, "title": "v1 — one line, now observed",
     "why": "Point the OpenAI client at the TapPass gateway (base_url swap). "
            "Nothing else changes.",
     "scenario": "happy",
     "watch": "Same answer — but now it's a governed turn with a full trace."},
    {"version": 2, "title": "v2 — stop data leaving",
     "why": "Policy now blocks PII / secrets in the agent's output.",
     "scenario": "governed",
     "watch": "The agent tries to read out a bank number → TapPass blocks it."},
    {"version": 3, "title": "v3 — gate the dangerous actions",
     "why": "The payment and bank-change write tools are blocked outright.",
     "scenario": "governed",
     "watch": "The agent tries to schedule a payment → blocked."},
    {"version": 4, "title": "v4 — human in the loop",
     "why": "Payments are allowed, but each one requires human approval.",
     "scenario": "governed",
     "watch": "The agent pauses for sign-off — you approve it (ENTER) and it "
              "proceeds; the approval + execution are audited."},
    {"version": 5, "title": "v5 — context-aware (the fraud beat)",
     "why": "Small payments flow; large ones need elevated approval; vendor "
            "bank-account changes ALWAYS need approval.",
     "scenario": "governed",
     "watch": "A €25k payment escalates for sign-off — approve it (ENTER) to "
              "resume. The classic AP-fraud guardrail."},
    {"version": 6, "title": "v6 — govern the agent that touches your catalog",
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


def _approve(name: str, args: dict, detail: dict) -> bool:
    """Human-in-the-loop sign-off, invoked when TapPass escalates a tool call.

    You are the reviewer TapPass escalated to — approving here (ENTER) is the
    in-script equivalent of approving in the dashboard. Ctrl-C denies.
    """
    tier = str(detail.get("tier", "elevated")).upper()
    reason = detail.get("reason", "approval required")
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
    print(f"  {GREEN}✓ approved — resuming the action{RESET}")
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
        org = cp.agent_org(s.agent_id) or ""
        policy_id, policy_name = cp.create_policy("AP Demo Policy", org_id=org)
        print(f"{GREEN}✓ fresh policy '{policy_name}' ({policy_id}){RESET}")

    policy_url = f"{s.url}/app/policies/{policy_id}"
    agent_url = f"{s.url}/app/agents/{s.agent_uuid}"

    print(f"\n{BOLD}TapPass · Accounts-Payable agent governance demo{RESET}")
    print(f"{DIM}Agent:  {agent_url}{RESET}")
    print(f"{DIM}Policy: {policy_url}{RESET}")
    print(f"{DIM}Press ENTER through v0→v6. Keep the dashboard open alongside.{RESET}")
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
        sid = agent_mod.run(v, prompt, s, approve_cb=_approve)
        if v >= 1 and sid:
            print(f"\n  {CYAN}→ open the governed trace:{RESET} "
                  f"{s.url}/app/sessions/{sid}")
        _pause("  ↵  press ENTER for the next step")

    print(f"\n{CYAN}{RULE}{RESET}")
    print(f"{BOLD}That's the ladder.{RESET} Six policy versions, activated live — "
          "and the agent code never changed.")
    print(f"  Policy version history: {policy_url}")
    if fresh and policy_id != s.policy_id:
        print(f"\n  {DIM}This run used a fresh policy. To keep it as the default,"
              f" set in .env:{RESET}\n  TAPPASS_POLICY_ID={policy_id}")
    print()
