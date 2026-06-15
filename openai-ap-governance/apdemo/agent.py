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
    _drive(agent, prompt, config, s, version, approve_cb)
    return session_id


def _drive(agent, prompt: str, config: dict, s: Settings, version: int,
           approve_cb) -> None:
    """Invoke the agent and print the final message. Approval-resume is layered
    on in Task 8 (kept as a separate seam so the spike result picks the path)."""
    result = agent.invoke({"messages": [("system", SYSTEM), ("user", prompt)]}, config)
    final = result["messages"][-1]
    content = getattr(final, "content", final)
    print(f"\n[ASSISTANT] {content}")
