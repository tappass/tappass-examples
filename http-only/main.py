"""Plain HTTP with TapPass. No SDK needed.

TapPass exposes an OpenAI-compatible REST API.
Works with any HTTP client in any language.
"""

import os
import httpx

TAPPASS_URL = os.getenv("TAPPASS_URL", "http://localhost:9620")
TAPPASS_API_KEY = os.getenv("TAPPASS_API_KEY", "tp_...")

# --- Chat completion ---

response = httpx.post(
    f"{TAPPASS_URL}/v1/chat/completions",
    headers={"Authorization": f"Bearer {TAPPASS_API_KEY}"},
    json={
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": "What is the EU AI Act?"},
        ],
    },
    timeout=60,
)
response.raise_for_status()
data = response.json()

print("Content:", data["choices"][0]["message"]["content"][:200])

# TapPass governance metadata
tp = data.get("tappass", {})
print(f"Blocked: {tp.get('blocked', False)}")
print(f"Classification: {tp.get('classification', 'unknown')}")


# --- Report a tool execution ---

httpx.post(
    f"{TAPPASS_URL}/tools/executed",
    headers={"Authorization": f"Bearer {TAPPASS_API_KEY}"},
    json={
        "tool": "web_search",
        "arguments": {"query": "EU AI Act requirements"},
        "duration_ms": 342.5,
        "success": True,
    },
    timeout=10,
)
print("\nTool execution reported to audit trail.")
