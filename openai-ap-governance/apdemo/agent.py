"""The AP agent: OpenAI agentic loop, governed via TapPass.

Two governance touch-points (v1+):
  * the LLM call routes through the TapPass gateway (base_url swap) — so output
    PII/secret scanning (v2) and audit/cost happen on the chat itself;
  * every TOOL CALL is submitted to /v1/govern BEFORE it runs, and the verdict
    is honored: block -> don't run; require_approval obligation -> halt and
    surface it (a reviewer approves in the dashboard in production); allow -> run.

v0 talks to OpenAI directly with no governance — the ungoverned baseline.
"""
from __future__ import annotations

import json
import uuid

import httpx
from openai import OpenAI

from .config import Settings
from .tools import dispatch, tool_description, tools_for_version


def build_client_kwargs(version: int, s: Settings,
                        session_id: str | None = None) -> dict:
    """v0 talks to OpenAI directly; v1+ route through the TapPass gateway.

    For v1+ we pin an ``X-Session-Id`` header so every gateway chat call in this
    run correlates to ONE session (and the same id we send on the /v1/govern
    tool calls) — otherwise each chat call lands in its own session and the
    trace fragments.
    """
    if version == 0:
        if not s.openai_api_key:
            raise SystemExit("v0 needs OPENAI_API_KEY (direct OpenAI).")
        return {"api_key": s.openai_api_key}
    kwargs = {"base_url": f"{s.url}/v1", "api_key": s.require_agent_key()}
    if session_id:
        kwargs["default_headers"] = {"X-Session-Id": session_id}
    return kwargs


def govern_tool_call(s: Settings, name: str, args: dict, session_id: str) -> tuple[str, dict]:
    """Submit a TOOL_CALL to /v1/govern (decision-only). Returns (decision, detail)
    where decision is "allow" | "block" | "approval".

    The decision path returns allow/block and any obligations; a require_approval
    obligation means TapPass has determined a human reviewer must approve before
    this action runs. Fail closed: a governance outage blocks the tool.
    """
    behavior = {
        "type": "TOOL_CALL",
        "agent_id": s.agent_id,
        "session_id": session_id,
        "behavior_id": uuid.uuid4().hex,
        # server=None → the trace shows this as a local (in-process) tool;
        # description = the schema text the model reasoned over to pick the tool.
        "payload": {"tool": name, "args": args, "server": None,
                    "description": tool_description(name)},
    }
    try:
        r = httpx.post(
            f"{s.url}/v1/govern",
            headers={"Authorization": f"Bearer {s.require_agent_key()}"},
            json=behavior, timeout=30,
        )
    except Exception as e:
        return "block", {"reason": f"governance_unavailable: {type(e).__name__}"}
    if r.status_code >= 400:
        return "block", {"reason": f"governance_unavailable: HTTP {r.status_code}"}
    d = r.json()
    pipeline_id = d.get("pipeline_id") or ""
    if d.get("outcome") == "block":
        return "block", {"reason": d.get("reason") or "blocked"}
    for ob in d.get("obligations") or []:
        if ob.get("type") == "require_approval":
            return "approval", {"tier": ob.get("tier", "authenticated"),
                                "reason": ob.get("reason") or "approval required"}
    return "allow", {"pipeline_id": pipeline_id}


def report_tool_result(s: Settings, pipeline_id: str, session_id: str,
                       result: dict) -> None:
    """Report the tool's result back to TapPass (correlated by pipeline_id) so
    the session trace shows the execution, not just the decision."""
    if not pipeline_id:
        return
    try:
        httpx.post(
            f"{s.url}/v1/govern/execution",
            headers={"Authorization": f"Bearer {s.require_agent_key()}"},
            json={"pipeline_id": pipeline_id, "agent_id": s.agent_id,
                  "session_id": session_id,
                  "output_text": json.dumps(result), "ok": True},
            timeout=15,
        )
    except Exception:
        pass  # telemetry only — never break the run on a report failure


def _run_tool(name: str, args: dict) -> dict:
    try:
        return dispatch(name, args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def run(version: int, prompt: str, s: Settings, max_steps: int = 6) -> str:
    """Run one agent interaction. Returns the session_id (for the trace URL)."""
    session_id = f"apdemo-v{version}-{uuid.uuid4().hex[:8]}"
    client = OpenAI(**build_client_kwargs(version, s, session_id))
    schemas, _ = tools_for_version(version)
    print(f"# session: {session_id}")
    messages = [
        {"role": "system", "content":
         "You are an Accounts Payable assistant. Use tools when needed."},
        {"role": "user", "content": prompt},
    ]
    for _ in range(max_steps):
        try:
            resp = client.chat.completions.create(
                model=s.model, messages=messages, tools=schemas or None)
        except Exception as e:
            status = getattr(e, "status_code", None)
            body = getattr(getattr(e, "response", None), "text", None)
            if status is not None:
                print(f"\n[GATEWAY {status}] {body or e}")
            else:
                print(f"\n[ERROR] {type(e).__name__}: {e}")
            return session_id
        msg = resp.choices[0].message
        if not msg.tool_calls:
            print(f"\n[ASSISTANT] {msg.content}")
            return session_id
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            detail: dict = {}

            # v1+ : govern the tool call BEFORE running it.
            if version >= 1:
                decision, detail = govern_tool_call(s, name, args, session_id)
                if decision == "block":
                    print(f"[BLOCKED] {name}({args}) — {detail['reason']}")
                    result = {"governed": "blocked", "reason": detail["reason"]}
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result)})
                    continue
                if decision == "approval":
                    print(f"[APPROVAL REQUIRED] {name}({args}) — "
                          f"{detail['tier']} approval: {detail['reason']}")
                    print("  ↳ agent halts; a reviewer approves in the TapPass "
                          "dashboard before this runs.")
                    result = {"governed": "approval_required",
                              "tier": detail["tier"], "reason": detail["reason"]}
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps(result)})
                    continue
                print(f"[GOVERNED ✓] {name} allowed")

            print(f"[TOOL] {name}({args})")
            result = _run_tool(name, args)
            if version >= 1:
                report_tool_result(s, detail.get("pipeline_id", ""),
                                   session_id, result)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})
    print("\n[done: step budget reached]")
    return session_id
