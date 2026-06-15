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
    config = {"configurable": {"thread_id": session_id},
              "callbacks": [handler],
              "recursion_limit": max_steps * 2}
    _drive(agent, prompt, config, approve_cb, handler)
    return session_id


def _drive(agent, prompt: str, config: dict, approve_cb,
           handler: VerdictHandler, max_resumes: int = 3) -> None:
    """Run the agent, driving the approve-and-resume loop.

    Under ``tappass.govern(mode="enforce")`` a gated tool call raises
    ``GovernanceBlocked`` from inside the tool, which propagates out of
    ``agent.invoke`` (verified — LangGraph does not swallow it). When the block
    is an approval gate and a reviewer hook is present, we grant the EXACT action
    the agent just attempted (captured by the handler) and re-invoke on the same
    thread so the identical call re-governs to allow (approval-as-fact). A
    non-approval block, a declined approval, or no hook → surface and stop.
    """
    from tappass._govern_call import GovernanceBlocked

    messages = {"messages": [("system", SYSTEM), ("user", prompt)]}
    base_thread = (config.get("configurable") or {}).get("thread_id", "t")
    cfg = config
    for attempt in range(max_resumes + 1):
        try:
            result = agent.invoke(messages, cfg)
            print(f"\n[ASSISTANT] {getattr(result['messages'][-1], 'content', result)}")
            return
        except GovernanceBlocked as exc:
            reason = str(exc)
            if "approval" not in reason.lower() or approve_cb is None:
                return  # hard block (verdict already printed by the handler)
            if not handler.last_tool:
                return
            name, args = handler.last_tool
            if not approve_cb(name, args, {"reason": reason}):
                print("  ↳ agent halts; a reviewer approves before this runs.")
                return
            # Resume on a FRESH thread with the original prompt. When the tool
            # raised GovernanceBlocked, the checkpoint kept the assistant turn's
            # dangling tool_call with no tool result; continuing that thread sends
            # an invalid message sequence to the model ("Invalid request format").
            # A fresh thread re-plans and re-issues the now-granted (single-use)
            # call cleanly, which re-governs to allow.
            cfg = {**config, "configurable": {**(config.get("configurable") or {}),
                                              "thread_id": f"{base_thread}-r{attempt + 1}"}}
    print("\n[done: approval retries exhausted]")
