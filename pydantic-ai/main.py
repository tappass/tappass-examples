"""Pydantic AI agent with TapPass governance.

Every LLM call is governed via the TapPass OpenAI-compatible gateway.

Note: pydantic-ai's `output_type=BaseModel` path sends `response_format` on
the request, which the TapPass gateway currently rejects (extra_forbidden).
This example sticks to plain-text output until the gateway accepts the
`response_format` field — at which point you can swap `output_type=str` for
`output_type=PromptedOutput(RiskAssessment)` to get structured JSON back.
"""

import os

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

model = OpenAIChatModel(
    "gpt-4o-mini",
    provider=OpenAIProvider(
        base_url=f"{TAPPASS_URL}/v1",
        api_key=TAPPASS_API_KEY,
    ),
)

agent = Agent(
    model,
    system_prompt=(
        "You are a compliance analyst. Be concise: title, three findings, "
        "a risk level, and three recommended actions."
    ),
)

result = agent.run_sync("Analyze the impact of the EU AI Act on AI agent deployments")
print(result.output)
