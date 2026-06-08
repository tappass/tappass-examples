"""Per-version policy rule-sets. Pure functions; no network.

Each rule is {"kind": str, "ordinal": int, "payload": dict} matching the
TapPass v2 RuleSpec. Versions are cumulative in *intent*, but each version is
the COMPLETE rule-set that policy version N publishes (the server replaces the
active rule-set on publish).

Rule kinds + payload fields are grounded in tappass/kernel/policy/templates.py
and conditional.py.
"""
from __future__ import annotations

# Tools the agent is allowed to call once enforcement turns on (v3+). Reads only.
_READ_TOOLS = ["calculate", "lookup_vendor", "compute_invoice_total"]

_PAYMENT_THRESHOLD = 10000  # EUR; payments above this need approval (v5)


def rules_for_version(n: int) -> list[dict]:
    if n <= 1:
        return []  # v1 = allow-all (observability only)

    rules: list[dict] = []

    # v2+: secret scan + PII handling on model-bound content.
    rules.append({"kind": "BlockSecrets", "ordinal": 0, "payload": {}})
    rules.append({"kind": "BlockPII", "ordinal": 1, "payload": {"scope": "output"}})
    if n == 2:
        return rules

    # v3+: tool-call enforcement. Allow-list the read tools; the payment WRITE
    # is intentionally absent, so it is blocked until a later version permits it
    # under approval.
    allowed = list(_READ_TOOLS)
    if n >= 4:
        # From v4 on, schedule_payment is permitted but gated by approval below.
        allowed.append("schedule_payment")
    if n >= 5:
        allowed.append("update_vendor_bank_details")
    if n >= 6:
        allowed += ["set_asset_classification", "propose_schema_change"]
    rules.append({"kind": "AllowTool", "ordinal": 2, "payload": {"tools": allowed}})
    if n == 3:
        return rules

    # v4: blunt human-in-the-loop approval on every payment.
    if n == 4:
        rules.append({"kind": "RequireApproval", "ordinal": 3, "payload": {
            "tools": ["schedule_payment"],
            "tier": "authenticated",
            "reason": "AP payment requires reviewer approval",
        }})
        return rules

    # v5: context-aware. Bank-detail changes ALWAYS need elevated approval
    # (classic AP-fraud vector); payments only need approval over the threshold.
    if n >= 5:
        rules.append({"kind": "Conditional", "ordinal": 3, "payload": {
            "when": {"signal": "request.tool", "op": "eq",
                     "value": "update_vendor_bank_details"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "Vendor bank-detail change requires elevated approval"},
        }})
        # FALLBACK (if input.request.args.amount is not a signal — see Task 8):
        #   replace the rule below with
        #   {"kind":"RequireApproval","ordinal":4,
        #    "payload":{"tools":["schedule_payment"],"tier":"authenticated",
        #               "reason":"AP payment requires approval"}}
        rules.append({"kind": "Conditional", "ordinal": 4, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "schedule_payment"},
                {"signal": "request.args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD},
            ]},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": f"Payment over EUR {_PAYMENT_THRESHOLD} requires approval"},
        }})
    if n == 5:
        return rules

    # v6: same kernel now governs catalog edits. The agent may never WEAKEN a
    # classification (floor rule: block any attempt to set it below confidential),
    # and any schema change needs elevated approval.
    if n >= 6:
        rules.append({"kind": "Conditional", "ordinal": 5, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.args.classification", "op": "in",
                 "value": ["public", "internal"]},
            ]},
            "then": {"action": "block",
                     "reason": "agent may not weaken a data classification"},
        }})
        rules.append({"kind": "Conditional", "ordinal": 6, "payload": {
            "when": {"signal": "request.tool", "op": "eq", "value": "propose_schema_change"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "catalog schema change requires elevated approval"},
        }})
    return rules


def change_note(n: int) -> str:
    notes = {
        1: "v1: allow-all — observability only",
        2: "v2: secret scan + PII redaction on output",
        3: "v3: tool-call enforcement (gate the payment write)",
        4: "v4: human approval on payments",
        5: "v5: context-aware — bank changes + over-threshold payments need approval",
        6: "v6: govern the catalog — block classification weakening; approve schema changes",
    }
    return notes[n]
