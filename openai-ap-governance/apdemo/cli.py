"""apdemo CLI: setup | activate | run | status | teardown."""
from __future__ import annotations

import argparse
import sys

from . import agent as agent_mod
from .config import Settings
from .provision import ControlPlane, ensure_live, setup as provision_setup
from .scenarios import prompt_for


def _env_dump(values: dict) -> str:
    return "\n".join(f"{k}={v}" for k, v in values.items())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apdemo")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create (or reuse) agent + a fresh policy")

    a = sub.add_parser(
        "activate",
        help="create+publish+assign policy posture N (1..11) — one forward step")
    a.add_argument("--version", type=int, required=True, choices=range(1, 12))

    r = sub.add_parser("run", help="run the agent at version N (0..11)")
    r.add_argument("--version", type=int, required=True, choices=range(0, 12))
    r.add_argument("--scenario", choices=["happy", "governed", "long"],
                   default="happy")
    r.add_argument("--prompt", default=None)

    g = sub.add_parser("guide", help="interactive guided demo — press ENTER through v0→v8")
    g.add_argument("--fresh", action="store_true",
                   help="reset to a brand-new policy first (clean v1→v8 history; re-runnable)")
    sub.add_parser("status", help="show active policy + assignment")
    sub.add_parser("evidence",
                   help="compliance evidence report (governed decisions + approvals)")
    sub.add_parser("route-demo",
                   help="data residency: route PII prompts to the approved model")
    sub.add_parser("teardown", help="remove the demo agent + policy")

    ap = sub.add_parser(
        "approve",
        help="operator grant for a pending action (POST /v1/govern/approve)")
    ap.add_argument("--tool", required=True)
    ap.add_argument("--arg", action="append", default=[],
                    help="key=value (repeatable) — the exact tool args to approve")

    args = p.parse_args(argv)
    s = Settings.load()

    if args.cmd == "setup":
        out = provision_setup(s)
        print("# Add these to openai-ap-governance/.env:")
        print(_env_dump({
            "TAPPASS_AGENT_KEY": out["agent_key"],
            "TAPPASS_AGENT_UUID": out["agent_uuid"],
            "TAPPASS_POLICY_ID": out["policy_id"],
        }))
        print(f"# agent + policy '{out['policy_name']}' live in org {out['org_id']}")
        return 0

    if args.cmd == "activate":
        s = ensure_live(s)                       # self-heal: live agent + policy
        cp = ControlPlane(s)
        version_no = cp.activate(s.policy_id, args.version, s.agent_uuid)
        print(f"Governance posture v{args.version} is now active "
              f"(policy version_no={version_no}) and assigned to the agent.")
        return 0

    if args.cmd == "run":
        s = ensure_live(s)                       # self-heal before running
        prompt = args.prompt or prompt_for(args.version, args.scenario)
        print(f"# v{args.version} [{args.scenario}] prompt: {prompt}")
        # The long scenario needs a bigger step budget (many tool calls).
        max_steps = 16 if args.scenario == "long" else 6
        agent_mod.run(args.version, prompt, s, max_steps=max_steps)
        return 0

    if args.cmd == "guide":
        from .guide import run_guide
        s = ensure_live(s)                       # self-heal so it restores + works every run
        run_guide(s, fresh=args.fresh)
        return 0

    if args.cmd == "status":
        s = ensure_live(s)
        print(f"url={s.url} agent_uuid={s.agent_uuid} policy_id={s.policy_id} org={s.org}")
        return 0

    if args.cmd == "evidence":
        from .evidence import report
        s = ensure_live(s)
        report(s)
        return 0

    if args.cmd == "route-demo":
        from .routing import route_demo
        s = ensure_live(s)
        route_demo(s)
        return 0

    if args.cmd == "approve":
        import httpx
        s = ensure_live(s)
        kv = dict(a.split("=", 1) for a in args.arg)
        r = httpx.post(f"{s.url}/v1/govern/approve",
                       headers={"Authorization": f"Bearer {s.require_pat()}"},
                       json={"agent_id": s.agent_id, "tool": args.tool, "args": kv,
                             "scope": "always"},
                       timeout=15)
        print(f"approve {args.tool}({kv}) -> {r.status_code} {r.text[:160]}")
        return 0 if r.status_code < 400 else 1

    if args.cmd == "teardown":
        print("Teardown: delete the agent + policy in the dashboard, or extend "
              "ControlPlane with delete calls (see Task 10).", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
