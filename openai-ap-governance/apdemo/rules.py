"""Per-version policy rule-sets. Pure functions; no network.

Each rule is {"kind": str, "ordinal": int, "payload": dict} matching the
TapPass v2 RuleSpec. Each version is the COMPLETE rule-set that policy version N
publishes (publish replaces the active rule-set).

IMPORTANT — the kernel DEFAULTS TO ALLOW (ADR 0013). So enforcement is done with
positive *block* / *approval* rules, NOT with allow-lists: an ``AllowTool``
allow-list blocks nothing on its own because unlisted tools already default to
allow. We therefore gate writes with ``BlockTool`` / ``RequireApproval`` /
``Conditional``. Rule kinds + payloads are grounded in
tappass/kernel/policy/templates.py and conditional.py and verified live.

These rules are evaluated for TOOL_CALL behaviors the agent submits to
/v1/govern before executing each tool, AND for the LLM_CALL output scan
(BlockPII / BlockSecrets) on the gateway path.
"""
from __future__ import annotations

_WRITE_TOOLS = ["schedule_payment", "update_vendor_bank_details"]

_PAYMENT_THRESHOLD = 10000  # EUR; payments above this need approval (v5)


def _block_pii_and_secrets(o: int) -> list[dict]:
    return [
        {"kind": "BlockSecrets", "ordinal": o, "payload": {}},
        {"kind": "BlockPII", "ordinal": o + 1, "payload": {"scope": "output"}},
    ]


def rules_for_version(n: int) -> list[dict]:
    if n <= 1:
        return []  # v1 = allow-all (observability only)

    # v2+: secret scan + PII block on model-bound output.
    rules: list[dict] = _block_pii_and_secrets(0)
    if n == 2:
        return rules

    # v3: hard-block the write tools outright (default-allow kernel => BlockTool).
    if n == 3:
        rules.append({"kind": "BlockTool", "ordinal": 2,
                      "payload": {"tools": list(_WRITE_TOOLS)}})
        return rules

    # v4: payments allowed but require human approval; bank-changes still blocked.
    if n == 4:
        rules.append({"kind": "BlockTool", "ordinal": 2,
                      "payload": {"tools": ["update_vendor_bank_details"]}})
        rules.append({"kind": "RequireApproval", "ordinal": 3, "payload": {
            "tools": ["schedule_payment"],
            "tier": "authenticated",
            "reason": "AP payment requires reviewer approval",
        }})
        return rules

    # v5: context-aware. Bank-detail changes ALWAYS need elevated approval
    # (classic AP-fraud vector); payments need approval only over the threshold.
    if n >= 5:
        rules.append({"kind": "Conditional", "ordinal": 2, "payload": {
            "when": {"signal": "request.tool", "op": "eq",
                     "value": "update_vendor_bank_details"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "Vendor bank-detail change requires elevated approval"},
        }})
        rules.append({"kind": "Conditional", "ordinal": 3, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "schedule_payment"},
                {"signal": "request.tool_args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD},
            ]},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": f"Payment over EUR {_PAYMENT_THRESHOLD} requires approval"},
        }})
    if n == 5:
        return rules

    # v6: same kernel now governs catalog edits. The agent may never WEAKEN a
    # classification (floor rule: block any target below confidential), and any
    # schema change needs elevated approval.
    if n >= 6:
        rules.append({"kind": "Conditional", "ordinal": 4, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.tool_args.classification", "op": "in",
                 "value": ["public", "internal"]},
            ]},
            "then": {"action": "block",
                     "reason": "agent may not weaken a data classification"},
        }})
        rules.append({"kind": "Conditional", "ordinal": 5, "payload": {
            "when": {"signal": "request.tool", "op": "eq", "value": "propose_schema_change"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "catalog schema change requires elevated approval"},
        }})
    return rules


def change_note(n: int) -> str:
    notes = {
        1: "v1: allow-all — observability only",
        2: "v2: secret scan + PII block on output",
        3: "v3: tool-call enforcement (block the payment + bank-change writes)",
        4: "v4: human approval on payments (bank-change still blocked)",
        5: "v5: context-aware — bank changes + over-threshold payments need approval",
        6: "v6: govern the catalog — block classification weakening; approve schema changes",
    }
    return notes[n]
