"""LangChain callback handler that renders governance verdicts.

Governance decisions are made by tappass.govern() inside the tool wrapper; a block
surfaces as an exception on the tool. This handler is presentation-only — it never
makes a governance decision. It prints the demo's signature lines:
  [GOVERNED ✓ tool]   [BLOCKED reason]   [APPROVAL REQUIRED tier]
"""
from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler

GREEN = "\033[32m"; RED = "\033[31m"; YELLOW = "\033[33m"; DIM = "\033[2m"; RESET = "\033[0m"


def classify_error(message: str) -> tuple[str, str]:
    """Map a GovernanceBlocked message to (label, human_reason)."""
    msg = message.split("governance block:", 1)[-1].strip() or message
    low = msg.lower()
    if "approval" in low:
        return "APPROVAL REQUIRED", msg
    if "rate" in low:
        return "BLOCKED", "rate limit exceeded"
    return "BLOCKED", msg


class VerdictHandler(BaseCallbackHandler):
    def __init__(self, governed: bool = True) -> None:
        self.governed = governed

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        name = (serialized or {}).get("name", "tool")
        print(f"{DIM}[TOOL] {name}({input_str}){RESET}")

    def on_tool_end(self, output, **kwargs) -> None:
        if not self.governed:
            return
        name = kwargs.get("name", "tool")
        print(f"{GREEN}[GOVERNED ✓ {name}]{RESET}")

    def on_tool_error(self, error: BaseException, **kwargs) -> None:
        label, reason = classify_error(str(error))
        color = YELLOW if label.startswith("APPROVAL") else RED
        print(f"{color}[{label}] {reason}{RESET}")
