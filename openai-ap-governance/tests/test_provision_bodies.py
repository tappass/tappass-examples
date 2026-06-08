from apdemo.provision import (
    onboard_body, policy_body, version_body, assignment_body,
)


def test_onboard_body():
    b = onboard_body(agent_id="ap-demo-agent", org_id="tappass-6ab653",
                     owner_email="you@example.com")
    assert b["agent_id"] == "ap-demo-agent"
    assert b["org_id"] == "tappass-6ab653"
    assert b["owner_email"] == "you@example.com"
    assert b["framework"] == "custom"


def test_policy_body():
    b = policy_body(org_id="tappass-6ab653", name="AP Demo Policy")
    assert b == {"org_id": "tappass-6ab653", "name": "AP Demo Policy",
                 "description": "Incremental AP-agent governance demo"}


def test_version_body_carries_rules_and_note():
    b = version_body(3)
    assert b["change_note"].startswith("v3")
    assert any(r["kind"] == "AllowTool" for r in b["rules"])


def test_assignment_body_keys_on_agent_uuid():
    b = assignment_body(agent_uuid="ag_ABC123")
    assert b == {"scope_type": "agent", "scope_id": "ag_ABC123"}
