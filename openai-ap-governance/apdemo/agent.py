"""The AP agent: a LangGraph agent governed via TapPass — Collibra's exact shape.

Two governance touch-points (v1+), both one line of customer code:
  * ChatOpenAI(base_url=<gateway>) routes the LLM call through TapPass (audit, cost,
    output PII/secret scan);
  * tappass.govern(tools, mode="enforce", ...) governs every tool call via /v1/govern
    before it runs — a block raises GovernanceBlocked; an approval drives the
    approve-and-resume flow (see run() / approve handling).

v0 talks to OpenAI directly with unwrapped tools — the ungoverned baseline.
"""
from __future__ import annotations

import uuid

import tappass
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from .config import Settings
from .tools import tools_for_version
from .verdicts import VerdictHandler

SYSTEM = ("You are an Accounts Payable assistant. Use tools when needed. "
          "Make ONE tool call at a time and report what happened for each.")


def build_model(version: int, s: Settings, session_id: str) -> ChatOpenAI:
    if version == 0:
        if not s.openai_api_key:
            raise SystemExit("v0 needs OPENAI_API_KEY (direct OpenAI).")
        return ChatOpenAI(model=s.model, base_url="https://api.openai.com/v1",
                          api_key=s.openai_api_key)
    return ChatOpenAI(model=s.model, base_url=f"{s.url}/v1",
                      api_key=s.require_agent_key(),
                      default_headers={"X-Session-Id": session_id})


def build_tools(version: int, s: Settings, session_id: str) -> list:
    raw = tools_for_version(version)
    if version == 0:
        return raw                                   # ungoverned baseline
    return tappass.govern(raw, url=s.url, api_key=s.require_agent_key(),
                          mode="enforce", agent_id=s.agent_id,
                          session_id=session_id, user_id=s.owner_email)


def build_agent(version: int, s: Settings, session_id: str):
    model = build_model(version, s, session_id)
    tools = build_tools(version, s, session_id)
    # Disable parallel tool-calling so the agent makes ONE tool call at a time.
    # Otherwise the model batches several tool calls in a single turn and they
    # are governed ~milliseconds apart in a scrambled order, so the audit trail
    # (and the rate-limit count) shows them out of sequence. One-at-a-time keeps
    # the governed trace in the order the model intends.
    if tools:
        model = model.bind_tools(tools, parallel_tool_calls=False)
    return create_agent(model, tools=tools, checkpointer=MemorySaver())


def run(version: int, prompt: str, s: Settings, max_steps: int = 6,
        approve_cb=None) -> str:
    """Run one agent interaction. Returns the session_id (for the trace URL).

    On the approval beats (v6–v8) the SDK enforce wrapper holds the gated tool
    until a human decides. ``approve_cb(name, args, detail) -> bool`` is the
    scripted reviewer hook (the guide wires it to POST /v1/govern/approve); when
    None, the demo relies on a human approving in the dashboard. The resume
    mechanics are layered on in Task 8.
    """
    session_id = f"apdemo-v{version}-{uuid.uuid4().hex[:8]}"
    print(f"# session: {session_id}")
    agent = build_agent(version, s, session_id)
    handler = VerdictHandler(governed=version >= 1)
    _install_govern_capture(handler)
    config = {"configurable": {"thread_id": session_id},
              "callbacks": [handler],
              "recursion_limit": max_steps * 2}
    _drive(agent, prompt, config, approve_cb, handler)
    return session_id


def _install_govern_capture(handler) -> None:
    """Record the EXACT (tool, args) the SDK governs, onto handler.last_governed.

    The reviewer must grant the same fingerprint the agent's govern call used.
    on_tool_start gives the model's PRE-coercion args (e.g. iban as the number
    5566), but the SDK governs the POST-coercion value the tool schema produced
    (iban="5566"). Granting the pre-coercion args yields a different fingerprint,
    so the grant never matches. We wrap the SDK's behavior builder to capture the
    governed payload args verbatim, which always match the govern fingerprint.
    """
    import importlib
    g = importlib.import_module("tappass.govern")
    orig = getattr(g, "_apdemo_orig_build_tool_behavior", None) or g._build_tool_behavior
    g._apdemo_orig_build_tool_behavior = orig

    def _capture(info, args, kwargs, **kw):
        b = orig(info, args, kwargs, **kw)
        try:
            handler.last_governed = (b["payload"]["tool"], dict(b["payload"]["args"]))
        except Exception:
            pass
        return b

    g._build_tool_behavior = _capture


def _drive(agent, prompt: str, config: dict, approve_cb,
           handler: VerdictHandler, max_resumes: int = 3) -> None:
    """Run the agent, driving the approve-and-resume loop.

    Under ``tappass.govern(mode="enforce")`` a gated tool call raises from inside
    the tool, which propagates out of ``agent.invoke`` (LangGraph does not swallow
    it). ADR 0016: a require-approval gate raises ``ApprovalPending`` (the server
    returned ``needs_approval`` + a persisted request); a hard denial raises
    ``GovernanceBlocked``. On ApprovalPending with a reviewer hook, we approve the
    EXACT action the agent attempted (captured by the handler) and re-run on a
    FRESH thread so the identical call re-governs to allow. A denial, a declined
    approval, or no hook → surface and stop.
    """
    from tappass._govern_call import ApprovalPending, GovernanceBlocked

    messages = {"messages": [("system", SYSTEM), ("user", prompt)]}
    base_thread = (config.get("configurable") or {}).get("thread_id", "t")
    cfg = config
    for attempt in range(max_resumes + 1):
        try:
            result = agent.invoke(messages, cfg)
            print(f"\n[ASSISTANT] {getattr(result['messages'][-1], 'content', result)}")
            return
        except GovernanceBlocked:
            return  # hard denial (verdict already printed by the handler)
        except ApprovalPending as exc:
            if approve_cb is None:
                print("  ↳ agent halts; a reviewer approves before this runs.")
                return
            # Approve the EXACT args the SDK governed (post-coercion), not the
            # model's pre-coercion on_tool_start args — else the fingerprint
            # differs and the grant never matches.
            governed = getattr(handler, "last_governed", None) or handler.last_tool
            if not governed:
                return
            name, args = governed
            detail = {"reason": str(exc), "request_id": getattr(exc, "request_id", "")}
            if not approve_cb(name, args, detail):
                print("  ↳ agent halts; a reviewer approves before this runs.")
                return
            # Resume on a FRESH thread with the original prompt. The blocked turn's
            # checkpoint holds a dangling tool_call (no tool result); continuing it
            # sends an invalid message sequence to the model. A fresh thread re-plans
            # and re-issues the now-approved call, which re-governs to allow.
            cfg = {**config, "configurable": {**(config.get("configurable") or {}),
                                              "thread_id": f"{base_thread}-r{attempt + 1}"}}
    print("\n[done: approval retries exhausted]")
