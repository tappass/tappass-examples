from apdemo.provision import (
    onboard_body, policy_body, version_body, assignment_body,
)


def test_onboard_body():
    b = onboard_body(agent_id="ap-demo-agent", owner_email="you@example.com")
    assert b["agent_id"] == "ap-demo-agent"
    # org_id is intentionally omitted so the server resolves the resource org
    # from the PAT (the home org from /api/me can differ and cause a 403).
    assert "org_id" not in b
    assert b["owner_email"] == "you@example.com"
    assert b["framework"] == "custom"


def test_policy_body():
    b = policy_body(org_id="tappass-6ab653", name="AP Demo Policy")
    assert b == {"org_id": "tappass-6ab653", "name": "AP Demo Policy",
                 "description": "Incremental AP-agent governance demo"}


def test_version_body_carries_rules_and_note():
    b = version_body(5)
    assert b["change_note"].startswith("v5")
    assert any(r["kind"] == "BlockTool" for r in b["rules"])


def test_version_body_covers_new_ladder():
    for n in range(1, 9):
        body = version_body(n)
        assert "rules" in body and "change_note" in body
    # v8 carries the catalog-governance rules + the cumulative cowsay rate limit
    kinds = [r["kind"] for r in version_body(8)["rules"]]
    assert "Conditional" in kinds and "PerToolRateLimit" in kinds


def test_assignment_body_keys_on_agent_uuid():
    b = assignment_body(agent_uuid="ag_ABC123")
    assert b == {"scope_type": "agent", "scope_id": "ag_ABC123"}
