"""apdemo CLI: setup | activate | run | status | teardown."""
from __future__ import annotations

import argparse
import sys

from . import agent as agent_mod
from .config import Settings
from .provision import ControlPlane, setup as provision_setup
from .scenarios import prompt_for


def _env_dump(values: dict) -> str:
    return "\n".join(f"{k}={v}" for k, v in values.items())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apdemo")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create agent + policy with 6 versions")

    a = sub.add_parser("activate", help="publish + assign policy version N (1..6)")
    a.add_argument("--version", type=int, required=True, choices=range(1, 7))

    r = sub.add_parser("run", help="run the agent at version N (0..6)")
    r.add_argument("--version", type=int, required=True, choices=range(0, 7))
    r.add_argument("--scenario", choices=["happy", "governed"], default="happy")
    r.add_argument("--prompt", default=None)

    sub.add_parser("status", help="show active policy + assignment")
    sub.add_parser("teardown", help="remove the demo agent + policy")

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
        print(f"# version_map: {out['version_map']}")
        return 0

    if args.cmd == "activate":
        cp = ControlPlane(s)
        if not s.policy_id or not s.agent_uuid:
            raise SystemExit("Run `apdemo setup` and fill .env first.")
        cp.publish(s.policy_id, args.version)
        cp.assign(s.policy_id, s.agent_uuid)
        print(f"Activated + assigned policy version {args.version}.")
        return 0

    if args.cmd == "run":
        prompt = args.prompt or prompt_for(args.version, args.scenario)
        print(f"# v{args.version} [{args.scenario}] prompt: {prompt}")
        agent_mod.run(args.version, prompt, s)
        return 0

    if args.cmd == "status":
        print(f"url={s.url} agent_uuid={s.agent_uuid} policy_id={s.policy_id}")
        return 0

    if args.cmd == "teardown":
        print("Teardown: delete the agent + policy in the dashboard, or extend "
              "ControlPlane with delete calls (see Task 10).")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
