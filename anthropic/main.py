"""Anthropic Claude with TapPass governance.

TapPass has a native Anthropic Messages API gateway.
Point the SDK at TapPass and all calls are governed.
"""

import os
import anthropic

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Point Anthropic SDK at TapPass ---

client = anthropic.Anthropic(
    base_url=TAPPASS_URL,
    api_key=TAPPASS_API_KEY,
)

# Standard message. Now governed.
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "What are the key GDPR requirements for AI systems?"},
    ],
)

print(message.content[0].text)


# --- Streaming ---

print("\nStreaming:")
with client.messages.stream(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Summarize the EU AI Act in 3 sentences."},
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
print()
