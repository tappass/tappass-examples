"""LangChain ReAct agent with TapPass governance.

LLM calls go through the governance pipeline.
Tool calls are logged to the audit trail.
"""

import os
from tappass import Agent

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Connect to TapPass ---

tp = Agent(TAPPASS_URL, TAPPASS_API_KEY)

# LLM pointing at TapPass gateway
llm = ChatOpenAI(
    base_url=tp.gateway_url,
    api_key=tp.api_key,
    model="gpt-4o-mini",
)


# --- Define tools ---

@tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}\n1. EU AI Act overview\n2. GDPR compliance for AI"

@tool
def calculate(expression: str) -> str:
    """Evaluate a math expression."""
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"


# Wrap tools with governance
governed_tools = tp.govern([search_web, calculate])


# --- Create and run agent ---

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful research assistant. Use tools when needed."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, governed_tools, prompt)
executor = AgentExecutor(agent=agent, tools=governed_tools, verbose=True)

result = executor.invoke({
    "input": "What are the key EU AI Act requirements? Calculate 2025 * 12."
})
print("\nAnswer:", result["output"])
