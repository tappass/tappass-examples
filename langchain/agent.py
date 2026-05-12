"""Minimal LangChain agent governed by TapPass.

- LLM calls go through the TapPass gateway (policy + audit).
- Tool calls are wrapped with `tappass.govern` (enforce — policy can block).

LangChain 1.x API: `create_agent` returns a compiled LangGraph state graph.
"""

import os
import tappass
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent

TAPPASS_URL = os.environ["TAPPASS_URL"]
TAPPASS_API_KEY = os.environ["TAPPASS_API_KEY"]

llm = ChatOpenAI(
    base_url=f"{TAPPASS_URL}/v1",
    api_key=TAPPASS_API_KEY,
    model="gpt-4o-mini",
)


@tool
def list_tables(domain: str) -> str:
    """List tables in a Collibra domain."""
    return f"customers, orders, payments (in {domain})"


@tool
def describe_table(table: str) -> str:
    """Return the schema of a table."""
    return f"{table}(id: uuid, created_at: timestamp, email: text)"


tools = tappass.govern(
    [list_tables, describe_table],
    url=TAPPASS_URL,
    api_key=TAPPASS_API_KEY,
    mode="enforce",
    agent_id="catalog-assistant",
)

agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are a data catalog assistant. Use tools to answer.",
)

if __name__ == "__main__":
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What columns does the customers table have?"}]}
    )
    print("\nAnswer:", result["messages"][-1].content)
