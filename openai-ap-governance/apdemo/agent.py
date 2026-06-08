"""The AP agent: OpenAI agentic loop, governed via the TapPass gateway (v1+)."""
from __future__ import annotations

import json

from openai import OpenAI

from .config import Settings
from .tools import dispatch, tools_for_version


def build_client_kwargs(version: int, s: Settings) -> dict:
    """v0 talks to OpenAI directly; v1+ route through the TapPass gateway."""
    if version == 0:
        if not s.openai_api_key:
            raise SystemExit("v0 needs OPENAI_API_KEY (direct OpenAI).")
        return {"api_key": s.openai_api_key}
    return {"base_url": f"{s.url}/v1", "api_key": s.require_agent_key()}


def run(version: int, prompt: str, s: Settings, max_steps: int = 6) -> None:
    client = OpenAI(**build_client_kwargs(version, s))
    schemas, _ = tools_for_version(version)
    messages = [
        {"role": "system", "content":
         "You are an Accounts Payable assistant. Use tools when needed."},
        {"role": "user", "content": prompt},
    ]
    for _ in range(max_steps):
        try:
            resp = client.chat.completions.create(
                model=s.model, messages=messages, tools=schemas or None)
        except Exception as e:
            # NOTE: the exact wire shape of a TapPass gateway block/redaction/approval
            # on /v1/chat/completions is confirmed in the live verification task; until
            # then, surface the real error instead of calling everything "governance".
            status = getattr(e, "status_code", None)
            body = getattr(getattr(e, "response", None), "text", None)
            if status is not None:
                print(f"\n[GATEWAY {status}] {body or e}")
            else:
                print(f"\n[ERROR] {type(e).__name__}: {e}")
            return
        msg = resp.choices[0].message
        if not msg.tool_calls:
            print(f"\n[ASSISTANT] {msg.content}")
            return
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print(f"[TOOL] {tc.function.name}({args})")
            try:
                result = dispatch(tc.function.name, args)
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})
    print("\n[done: step budget reached]")
