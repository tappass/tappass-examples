"""OpenAI SDK with TapPass governance.

Change base_url to point at TapPass. That's it.
Every call now runs through the governance pipeline.
"""

import os
from openai import OpenAI

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# Point OpenAI at TapPass gateway
client = OpenAI(
    base_url=f"{TAPPASS_URL}/v1",
    api_key=TAPPASS_API_KEY,
)

# Standard chat completion. Now governed.
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful analyst."},
        {"role": "user", "content": "What were the Q3 revenue trends?"},
    ],
)

print(response.choices[0].message.content)


# --- With function calling ---

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Search for AI governance papers"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "search_papers",
            "description": "Search academic papers",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }],
)

if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        print(f"Tool call: {tc.function.name}({tc.function.arguments})")
