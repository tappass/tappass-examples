"""OpenAI SDK streaming with TapPass governance."""

import os
from openai import OpenAI

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

client = OpenAI(
    base_url=f"{TAPPASS_URL}/v1",
    api_key=TAPPASS_API_KEY,
)

# Streaming. Governance runs first, then tokens stream through.
stream = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Write a haiku about AI security"}],
    stream=True,
)

for chunk in stream:
    content = chunk.choices[0].delta.content
    if content:
        print(content, end="", flush=True)
print()


# --- Using the TapPass SDK ---

from tappass import Agent

agent = Agent(TAPPASS_URL, TAPPASS_API_KEY)

for chunk in agent.stream("Now write one about data privacy"):
    print(chunk, end="", flush=True)
print()
