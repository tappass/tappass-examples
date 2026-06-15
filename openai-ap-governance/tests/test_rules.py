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
    assert rl["payload"] == {"tool": "cowsay", "max": 3, "window_seconds": 120}
    assert "Conditional" in _kinds(3)


def test_v4_adds_output_pii_secrets():
    assert {"BlockSecrets", "BlockPII"} <= set(_kinds(4))


def test_v5_blocks_payment_write():
    assert any(r["kind"] == "BlockTool" and "schedule_payment" in r["payload"]["tools"]
               for r in rules_for_version(5))


def _approval_gates(n):
    """Conditionals that block until granted (when includes subject.approval.granted)."""
    out = []
    for r in rules_for_version(n):
        if r["kind"] != "Conditional":
            continue
        leaves = r["payload"]["when"].get("all", [r["payload"]["when"]])
        if any(l.get("signal") == "subject.approval.granted" for l in leaves):
            out.append(r)
    return out


def test_v6_payment_needs_approval_via_block_until_granted():
    # Path B: approval is a block-when-ungranted Conditional, NOT a RequireApproval
    # obligation (which the SDK enforce path does not halt on). No blanket BlockTool.
    rs = rules_for_version(6)
    assert not any(r["kind"] == "RequireApproval" for r in rs)
    assert not any(r["kind"] == "BlockTool" for r in rs)
    gates = _approval_gates(6)
    assert len(gates) == 1
    g = gates[0]
    assert g["payload"]["then"]["action"] == "block"
    assert "approval required" in g["payload"]["then"]["reason"]
    leaves = g["payload"]["when"]["all"]
    assert {"signal": "request.tool", "op": "eq", "value": "schedule_payment"} in leaves


def test_v7_is_context_aware():
    # Bank-change always gated; payment gated only over the threshold — both as
    # block-until-granted Conditionals.
    gates = _approval_gates(7)
    tools = set()
    for g in gates:
        for l in g["payload"]["when"]["all"]:
            if l.get("signal") == "request.tool":
                tools.add(l["value"])
    assert {"update_vendor_bank_details", "schedule_payment"} <= tools
    # the payment gate carries the amount threshold
    assert any(any(l.get("signal") == "request.tool_args.amount" and l["op"] == "gt"
                   for l in g["payload"]["when"]["all"]) for g in gates)


def test_v8_governs_catalog():
    rs = rules_for_version(8)
    assert any(r["payload"]["then"].get("reason", "").startswith("agent may not weaken")
               for r in rs if r["kind"] == "Conditional")


def test_change_notes_cover_1_to_8():
    for n in range(1, 9):
        assert change_note(n)
