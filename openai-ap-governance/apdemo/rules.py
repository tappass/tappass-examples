"""Per-version policy rule-sets. Pure functions; no network.

Each rule is {"kind": str, "ordinal": int, "payload": dict} (TapPass v2 RuleSpec).
rules_for_version(n) returns the COMPLETE rule-set version n publishes. Rules are
cumulative EXCEPT where a later version refines an earlier control (v5 blocks the
payment; v6 supersedes that with approval; v7 makes approval context-aware).

The kernel DEFAULTS TO ALLOW (ADR 0013) — enforcement is positive block/approval
rules, never allow-lists. Kinds + payloads grounded in kernel/policy/templates.py,
conditional.py, signal_catalog.py, producers/tool_rate.py and verified live (Task 1).
"""
from __future__ import annotations

# v2 — govern the cow's words
_BANNED_PATTERN = "(?i)(voldemort|enron)"            # banned names the cow may not say
_REDACT_PATTERN = r"[\w.+-]+@[\w-]+\.[\w.-]+"        # scrub emails out of the message
# v3 — frequency
_RATE_TOOL, _RATE_MAX, _RATE_WINDOW_S = "cowsay", 3, 120
# v7 — payment threshold
_PAYMENT_THRESHOLD = 10000  # EUR


def _cowsay_rules(o: int) -> list[dict]:
    return [
        {"kind": "Conditional", "ordinal": o, "payload": {
            "when": {"signal": "request.tool_args.message", "op": "match",
                     "value": _BANNED_PATTERN},
            "then": {"action": "block", "reason": "the cow may not say that"}}},
        {"kind": "RedactToolArg", "ordinal": o + 1, "payload": {
            "matchers": [{"tool": "cowsay", "arg": "message", "pattern": _REDACT_PATTERN}]}},
    ]


def _rate_rules(o: int) -> list[dict]:
    return [{"kind": "PerToolRateLimit", "ordinal": o, "payload": {
        "tool": _RATE_TOOL, "max": _RATE_MAX, "window_seconds": _RATE_WINDOW_S}}]


def _pii_rules(o: int) -> list[dict]:
    return [
        {"kind": "BlockSecrets", "ordinal": o, "payload": {}},
        {"kind": "BlockPII", "ordinal": o + 1, "payload": {"scope": "output"}},
    ]


def rules_for_version(n: int) -> list[dict]:
    if n <= 1:
        return []                                    # v1 = allow-all (observe only)

    rules: list[dict] = _cowsay_rules(0)             # v2: block banned word + redact
    if n == 2:
        return rules

    rules += _rate_rules(2)                           # v3: cowsay rate limit
    if n == 3:
        return rules

    rules += _pii_rules(3)                            # v4: output PII/secret block

    # v5: block the payment write. v6: supersede with approval. v7+: context-aware.
    if n == 5:
        rules.append({"kind": "BlockTool", "ordinal": 5,
                      "payload": {"tools": ["schedule_payment"]}})
    elif n == 6:
        rules.append({"kind": "RequireApproval", "ordinal": 5, "payload": {
            "tools": ["schedule_payment"], "tier": "authenticated",
            "reason": "AP payment requires reviewer approval"}})
    elif n >= 7:
        rules.append({"kind": "Conditional", "ordinal": 5, "payload": {
            "when": {"signal": "request.tool", "op": "eq",
                     "value": "update_vendor_bank_details"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "vendor bank-detail change requires elevated approval"}}})
        rules.append({"kind": "Conditional", "ordinal": 6, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "schedule_payment"},
                {"signal": "request.tool_args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD}]},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": f"payment over EUR {_PAYMENT_THRESHOLD} requires approval"}}})

    if n >= 8:
        rules.append({"kind": "Conditional", "ordinal": 7, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.tool_args.classification", "op": "in",
                 "value": ["public", "internal"]}]},
            "then": {"action": "block", "reason": "agent may not weaken a data classification"}}})
        rules.append({"kind": "Conditional", "ordinal": 8, "payload": {
            "when": {"signal": "request.tool", "op": "eq", "value": "propose_schema_change"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "catalog schema change requires elevated approval"}}})
    return rules


def change_note(n: int) -> str:
    notes = {
        1: "v1: allow-all — observability only",
        2: "v2: govern the cow's words — block a banned name, redact emails",
        3: "v3: rate-limit cowsay (3 calls / 2 min, from the audit trail)",
        4: "v4: secret scan + PII block on output",
        5: "v5: tool-call enforcement — block the payment write",
        6: "v6: human approval on payments (escalate → approve → resume)",
        7: "v7: context-aware — bank changes + over-threshold payments need approval",
        8: "v8: govern the catalog — block classification weakening; approve schema changes",
    }
    return notes[n]
