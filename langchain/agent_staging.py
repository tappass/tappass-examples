"""LangChain agent + MCP + TapPass governance, end-to-end against staging.

What this demonstrates
----------------------

A LangChain ReAct agent talks to a *real* MCP server (``collibra_mcp_server.py``,
spawned as a subprocess over stdio) that exposes Collibra-flavoured metadata
tools: list_tables, create_table, create_column, attach_classification,
delete_asset.

Every tool call the agent makes is governed by TapPass at the per-call
level (``tappass.govern(mode="enforce")``). The pipeline asks OPA whether
the call is allowed *given the actual tool arguments*. Two scenarios run
back-to-back:

  • Scenario A (allowed) — "add a table called 'campaigns' to schema
    'marketing'". Policy says ``marketing`` is on the write allowlist,
    so OPA returns allow=true and the MCP call executes.

  • Scenario B (blocked) — "add a table called 'invoices' to schema
    'finance'". Policy says ``finance`` is NOT on the allowlist, so OPA
    returns allow=false with a deny reason. The SDK raises
    ``GovernanceBlocked`` before the MCP call ever runs; LangChain surfaces
    it back to the LLM as a tool error, and the LLM tells the user what
    happened.

The same governed-tools wrapping would apply to any MCP server — the agent
code doesn't change when you swap Collibra for Atlan, Snowflake, or your
own internal catalog.

Prerequisites
-------------

1. ``.env`` populated (URL + dev key + agent_id).
2. The project the agent belongs to has the policy from
   ``collibra_policy.json`` configured on staging. Without it, BOTH
   scenarios succeed and the demo loses its point.

Run
---

    .venv/bin/python agent_staging.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import tappass
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI


# ── .env loader ───────────────────────────────────────────────────────
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


HERE = Path(__file__).parent
_load_env_file(HERE / ".env")

TAPPASS_URL = os.environ["TAPPASS_URL"]
TAPPASS_API_KEY = os.environ["TAPPASS_API_KEY"]
TAPPASS_AGENT_ID = os.environ.get("TAPPASS_AGENT_ID", "langchain-demo")

if TAPPASS_API_KEY.startswith("tp_PASTE"):
    raise SystemExit(
        f"TAPPASS_API_KEY is still the placeholder — paste the staging dev key "
        f"into {HERE / '.env'} first."
    )


# ── MCP wiring ────────────────────────────────────────────────────────
# Spawn the Collibra MCP server as a subprocess using the same Python that's
# running this script (i.e. our venv). Transport is stdio — the LangChain
# adapter speaks the MCP JSON-RPC protocol over the subprocess's stdin/stdout.
VENV_PYTHON = Path(sys.executable)
MCP_SERVER_PATH = HERE / "collibra_mcp_server.py"


async def main() -> None:
    print(f"→ Agent: {TAPPASS_AGENT_ID}  |  Gateway: {TAPPASS_URL}")
    print(f"→ MCP server: {MCP_SERVER_PATH.name} (spawned via {VENV_PYTHON.name})\n")

    client = MultiServerMCPClient({
        "collibra": {
            "command": str(VENV_PYTHON),
            "args": [str(MCP_SERVER_PATH)],
            "transport": "stdio",
        },
    })
    mcp_tools = await client.get_tools()
    print(f"→ Loaded {len(mcp_tools)} tools from MCP: "
          + ", ".join(t.name for t in mcp_tools) + "\n")

    # Wrap every MCP tool with TapPass governance. In enforce mode, every
    # invocation does a synchronous POST to /v1/govern *before* the tool
    # runs. OPA sees the tool name + arg dict and returns allow/deny.
    governed_tools = tappass.govern(
        mcp_tools,
        url=TAPPASS_URL,
        api_key=TAPPASS_API_KEY,
        mode="enforce",
        agent_id=TAPPASS_AGENT_ID,
    )

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        base_url=f"{TAPPASS_URL}/v1",
        api_key=TAPPASS_API_KEY,
    )
    agent = create_agent(
        model=llm,
        tools=governed_tools,
        system_prompt=(
            "You are a data-catalog assistant for a Collibra-style metadata "
            "platform. Use the available tools to fulfill requests. If a "
            "tool call is rejected by the governance policy, tell the user "
            "exactly why (quote the deny reason) instead of retrying."
        ),
    )

    scenarios = [
        ("A — allowed (schema=marketing)",
         "Register a new table called 'campaigns' in the marketing schema. "
         "Give it the description 'Outbound campaign tracking'."),
        ("B — blocked (schema=finance)",
         "Register a new table called 'invoices' in the finance schema with "
         "the description 'AP invoice register'."),
    ]

    for label, prompt in scenarios:
        print("─" * 72)
        print(f"Scenario {label}")
        print(f"  user: {prompt}")
        result = await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        final = result["messages"][-1].content
        print(f"  agent: {final}\n")

    print("─" * 72)
    print(f"See the session timeline at {TAPPASS_URL}/app/sessions")


if __name__ == "__main__":
    asyncio.run(main())
