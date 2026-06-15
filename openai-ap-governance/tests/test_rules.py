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


def test_v6_requires_approval_on_payment_not_block():
    rs = rules_for_version(6)
    assert any(r["kind"] == "RequireApproval" for r in rs)
    assert not any(r["kind"] == "BlockTool" for r in rs)


def test_v7_is_context_aware():
    conds = [r for r in rules_for_version(7) if r["kind"] == "Conditional"]
    actions = {r["payload"]["then"]["action"] for r in conds}
    assert "require_approval" in actions


def test_v8_governs_catalog():
    rs = rules_for_version(8)
    assert any(r["payload"]["then"].get("reason", "").startswith("agent may not weaken")
               for r in rs if r["kind"] == "Conditional")


def test_change_notes_cover_1_to_8():
    for n in range(1, 9):
        assert change_note(n)
