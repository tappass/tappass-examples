from apdemo.rules import rules_for_version, _PAYMENT_THRESHOLD


def test_v1_is_allow_all():
    assert rules_for_version(1) == []


def test_v2_has_secrets_and_pii():
    kinds = [r["kind"] for r in rules_for_version(2)]
    assert "BlockSecrets" in kinds
    assert "BlockPII" in kinds


def test_v3_blocks_payment_write():
    # The kernel defaults to ALLOW, so the write is gated with BlockTool
    # (an allow-list would block nothing).
    rs = rules_for_version(3)
    block = next(r for r in rs if r["kind"] == "BlockTool")
    assert "schedule_payment" in block["payload"]["tools"]
    assert "update_vendor_bank_details" in block["payload"]["tools"]
    assert "lookup_vendor" not in block["payload"]["tools"]


def test_v4_requires_approval_on_payment():
    rs = rules_for_version(4)
    appr = next(r for r in rs if r["kind"] == "RequireApproval")
    assert "schedule_payment" in appr["payload"]["tools"]
    assert appr["payload"]["tier"] in ("authenticated", "elevated")


def test_v5_conditional_bank_change_and_threshold():
    rs = rules_for_version(5)
    conds = [r for r in rs if r["kind"] == "Conditional"]
    # one rule keys on the bank-detail tool, one on the payment amount
    signals = [_leaf_signals(c["payload"]["when"]) for c in conds]
    flat = {s for group in signals for s in group}
    assert "request.tool" in flat

    # Also assert the amount-threshold rule is present and correct. Tool args
    # are exposed to Rego under request.tool_args.* (NOT request.args.*).
    leaves = [leaf for c in conds for leaf in _leaf_triples(c["payload"]["when"])]
    signals_only = {sig for sig, _, _ in leaves}
    assert "request.tool_args.amount" in signals_only
    assert any(op == "gt" and val == _PAYMENT_THRESHOLD
               for _, op, val in leaves)


def test_v6_blocks_weak_classification():
    rs = rules_for_version(6)
    cond = next(r for r in rs if r["kind"] == "Conditional"
                and r["payload"]["then"]["action"] == "block")
    assert cond["payload"]["then"]["action"] == "block"


def _leaf_signals(node):
    if "signal" in node:
        return [node["signal"]]
    key = "all" if "all" in node else "any"
    out = []
    for child in node.get(key, []):
        out += _leaf_signals(child)
    return out


def _leaf_triples(node):
    """Return (signal, op, value) tuples for all leaf nodes."""
    if "signal" in node:
        return [(node["signal"], node.get("op"), node.get("value"))]
    key = "all" if "all" in node else "any"
    out = []
    for child in node.get(key, []):
        out += _leaf_triples(child)
    return out
