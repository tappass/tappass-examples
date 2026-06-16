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
# Scrub an internal reference code (e.g. ACME-4471) out of the message — a
# "redact what's sensitive" beat that, unlike an email, is NOT independently
# flagged by PII/secret detection, so it shows as allow+redacted rather than a
# PII block. ASCII-only ON PURPOSE: a Unicode `\w` class expands so far in
# regorus's regex engine that the compiled program exceeds its 100 KB limit and
# the whole policy fails closed (`policy_eval_failed`). Keep tool-arg regexes
# ASCII so they compile small. The shape (2+ caps, dash, 3+ alnum) avoids vendor
# ids like V-1001 / INV-77.
_REDACT_PATTERN = r"[A-Z]{2,}-[A-Z0-9]{3,}"
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



def _tool_is(tool: str) -> dict:
    return {"signal": "request.tool", "op": "eq", "value": tool}


def _and(*leaves: dict) -> list[dict]:
    return list(leaves)


def _approval_gate(o: int, when_leaves: list[dict], *, reason: str) -> dict:
    """A Conditional that REQUIRES human approval for the matching action.

    `require_approval when (… matching leaves …)`. The conditional compiler gates
    the require_approval obligation on `subject.approval.granted != true`
    automatically (and selects the ApprovalProducer), so the decision-only
    /v1/govern returns a first-class `needs_approval` outcome + a persisted
    pending request while ungranted (ADR 0016), then `allow` once approved. The
    SDK raises `ApprovalPending` on needs_approval; the agent grants the exact
    action (POST /v1/govern/approve, which idempotently approves that pending
    request) and re-submits, which re-governs to allow."""
    return {"kind": "Conditional", "ordinal": o, "payload": {
        "when": {"all": list(when_leaves)},
        "then": {"action": "require_approval", "tier": "elevated", "reason": reason}}}


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
    #
    # Approval is a `require_approval` Conditional (ADR 0016): the decision-only
    # /v1/govern returns a first-class `needs_approval` outcome + a persisted
    # pending request while ungranted; the SDK raises `ApprovalPending`; a reviewer
    # approves; the identical re-submit re-governs to `allow`. The conditional
    # compiler suppresses the obligation once `subject.approval.granted` is true.
    if n == 5:
        rules.append({"kind": "BlockTool", "ordinal": 5,
                      "payload": {"tools": ["schedule_payment"]}})
    elif n == 6:
        rules.append(_approval_gate(5, _and(
            _tool_is("schedule_payment")),
            reason="approval required: AP payment needs reviewer sign-off"))
    elif n >= 7:
        rules.append(_approval_gate(5, _and(
            _tool_is("update_vendor_bank_details")),
            reason="approval required: vendor bank-detail change (elevated)"))
        rules.append(_approval_gate(6, _and(
            _tool_is("schedule_payment"),
            {"signal": "request.tool_args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD}),
            reason=f"approval required: payment over EUR {_PAYMENT_THRESHOLD} (elevated)"))

    if n >= 8:
        rules.append({"kind": "Conditional", "ordinal": 7, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.tool_args.classification", "op": "in",
                 "value": ["public", "internal"]}]},
            "then": {"action": "block", "reason": "agent may not weaken a data classification"}}})
        rules.append(_approval_gate(8, _and(
            _tool_is("propose_schema_change")),
            reason="approval required: catalog schema change (elevated)"))
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
