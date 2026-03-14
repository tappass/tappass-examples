"""Pydantic AI agent with TapPass governance.

Structured output with type safety. Every LLM call is governed.
"""

import os
from tappass import Agent as TapPassAgent

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Connect to TapPass ---

tp = TapPassAgent(TAPPASS_URL, TAPPASS_API_KEY)

model = OpenAIModel(
    "gpt-4o-mini",
    base_url=tp.gateway_url,
    api_key=tp.api_key,
)


# --- Define output schema ---

class RiskAssessment(BaseModel):
    title: str
    key_findings: list[str]
    risk_level: str  # low, medium, high
    recommended_actions: list[str]


# --- Create and run agent ---

agent = Agent(
    model,
    result_type=RiskAssessment,
    system_prompt=(
        "You are a compliance analyst. Analyze topics and return "
        "structured risk assessments."
    ),
)

result = agent.run_sync("Analyze the impact of the EU AI Act on AI agent deployments")

assessment = result.data
print(f"Title: {assessment.title}")
print(f"Risk: {assessment.risk_level}")
for finding in assessment.key_findings:
    print(f"  - {finding}")
for action in assessment.recommended_actions:
    print(f"  > {action}")
