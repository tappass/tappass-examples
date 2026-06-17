from apdemo.rules import rules_for_version, change_note


def _kinds(n):
    return [r["kind"] for r in rules_for_version(n)]


def test_v0_v1_have_no_rules():
    assert rules_for_version(0) == [] and rules_for_version(1) == []


def test_v2_blocks_banned_message_and_redacts():
    rs = rules_for_version(2)
    cond = next(r for r in rs if r["kind"] == "Conditional")
    assert cond["payload"]["when"]["signal"] == "request.tool_args.message"
    assert cond["payload"]["then"]["action"] == "block"
    assert any(r["kind"] == "RedactToolArg" for r in rs)


def test_v3_adds_cowsay_rate_limit():
    rl = next(r for r in rules_for_version(3) if r["kind"] == "PerToolRateLimit")
    assert rl["payload"] == {"tool": "send_reminder", "max": 3, "window_seconds": 30}
    assert "Conditional" in _kinds(3)


def test_v4_adds_output_pii_secrets():
    # v4 guards the OUTPUT: response-scanning kinds (block PII/secrets that would
    # leak in the model's response), NOT input-PII rules — so v11 can route input
    # PII without v4 shadowing it.
    assert {"BlockResponseSecrets", "BlockResponsePII"} <= set(_kinds(4))
    assert "BlockPII" not in _kinds(4)


def test_v5_blocks_payment_write():
    assert any(r["kind"] == "BlockTool" and "schedule_payment" in r["payload"]["tools"]
               for r in rules_for_version(5))


def _approval_gates(n):
    """Conditionals whose action is require_approval (ADR 0016 → needs_approval)."""
    return [r for r in rules_for_version(n)
            if r["kind"] == "Conditional"
            and r["payload"]["then"].get("action") == "require_approval"]


def test_v6_payment_needs_approval_via_require_approval():
    # ADR 0016: approval is a require_approval Conditional → the decision-only
    # /v1/govern returns needs_approval. No block-hack, no blanket BlockTool.
    rs = rules_for_version(6)
    assert not any(r["kind"] == "BlockTool" for r in rs)
    gates = _approval_gates(6)
    assert len(gates) == 1
    g = gates[0]
    assert g["payload"]["then"]["action"] == "require_approval"
    assert g["payload"]["then"]["tier"] and "approval required" in g["payload"]["then"]["reason"]
    leaves = g["payload"]["when"]["all"]
    assert {"signal": "request.tool", "op": "eq", "value": "schedule_payment"} in leaves
    # the compiler auto-gates require_approval on subject.approval.granted — the rule
    # itself must NOT carry an explicit granted leaf.
    assert not any(l.get("signal") == "subject.approval.granted" for l in leaves)


def test_v7_is_context_aware():
    # Bank-change always needs approval; payment only over the threshold.
    gates = _approval_gates(7)
    tools = set()
    for g in gates:
        for l in g["payload"]["when"]["all"]:
            if l.get("signal") == "request.tool":
                tools.add(l["value"])
    assert {"update_vendor_bank_details", "schedule_payment"} <= tools
    assert any(any(l.get("signal") == "request.tool_args.amount" and l["op"] == "gt"
                   for l in g["payload"]["when"]["all"]) for g in gates)


def test_v8_governs_catalog():
    rs = rules_for_version(8)
    assert any(r["payload"]["then"].get("reason", "").startswith("agent may not weaken")
               for r in rs if r["kind"] == "Conditional")


def test_change_notes_cover_1_to_11():
    for n in range(1, 12):
        assert change_note(n)


def _conds(n):
    return [r for r in rules_for_version(n) if r["kind"] == "Conditional"]


def test_v9_blocks_export_of_restricted_asset():
    # The block list is derived from the catalog's Restricted classifications.
    from apdemo import catalog
    g = next(r for r in _conds(9)
             if {"signal": "request.tool", "op": "eq", "value": "export_asset"}
             in r["payload"]["when"].get("all", []))
    assert g["payload"]["then"]["action"] == "block"
    leaf = next(l for l in g["payload"]["when"]["all"]
                if l.get("signal") == "request.tool_args.asset_id")
    assert leaf["op"] == "in" and leaf["value"] == catalog.restricted_asset_ids()
    assert "vendor_bank_accounts" in leaf["value"]


def test_v10_blocks_prompt_injection():
    g = next(r for r in _conds(10)
             if r["payload"]["when"].get("signal") == "findings.injection_score")
    assert g["payload"]["when"]["op"] == "gt"
    assert g["payload"]["then"]["action"] == "block"


def test_v11_routes_pii_to_approved_model():
    g = next(r for r in _conds(11)
             if r["payload"]["when"].get("signal") == "findings.pii")
    then = g["payload"]["then"]
    assert then["action"] == "route_to_model" and then.get("model")
