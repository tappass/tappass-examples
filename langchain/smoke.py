"""One-shot smoke test: a single ChatOpenAI call through the TapPass gateway.

Validates that {.env, key, gateway, BYOK LLM key} are all wired up before
moving to the full governed agent in agent_staging.py.
"""

import os
from pathlib import Path

from langchain_openai import ChatOpenAI


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_env_file(Path(__file__).parent / ".env")

llm = ChatOpenAI(
    model="gpt-4o",
    base_url=f"{os.environ['TAPPASS_URL']}/v1",
    api_key=os.environ["TAPPASS_API_KEY"],
)

result = llm.invoke("What is agent governance?")
print(result.content)
