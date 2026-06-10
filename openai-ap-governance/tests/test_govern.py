"""Unit tests for govern_tool_call verdict parsing (no network)."""
import apdemo.agent as agent_mod
from apdemo.config import Settings


def _settings():
    return Settings(
        url="https://app.tappass.ai", pat=None, agent_key="tp_dev_x",
        agent_uuid="ag_1", agent_id="ap-demo-agent", policy_id="p1",
        model="gpt-4o-mini", openai_api_key="sk-test", owner_email="d@e.com")


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _patch(monkeypatch, status, payload):
    monkeypatch.setattr(agent_mod.httpx, "post",
                        lambda *a, **k: _Resp(status, payload))


def test_block_outcome(monkeypatch):
    _patch(monkeypatch, 200, {"outcome": "block", "reason": "blocked_tool:x"})
    decision, detail = agent_mod.govern_tool_call(_settings(), "x", {}, "s")
    assert decision == "block"
    assert detail["reason"] == "blocked_tool:x"


def test_require_approval_obligation(monkeypatch):
    _patch(monkeypatch, 200, {"pipeline_id": "run_abc", "outcome": "allow",
        "obligations": [
            {"type": "require_approval", "tier": "elevated", "reason": "needs sign-off"}]})
    decision, detail = agent_mod.govern_tool_call(_settings(), "pay", {}, "s")
    assert decision == "approval"
    assert detail["tier"] == "elevated"
    assert detail["reason"] == "needs sign-off"
    # approval detail carries pipeline_id so an approved action can be reported
    assert detail["pipeline_id"] == "run_abc"


def test_allow(monkeypatch):
    _patch(monkeypatch, 200, {"outcome": "allow", "obligations": []})
    decision, _ = agent_mod.govern_tool_call(_settings(), "calc", {}, "s")
    assert decision == "allow"


def test_fail_closed_on_http_error(monkeypatch):
    _patch(monkeypatch, 503, {})
    decision, detail = agent_mod.govern_tool_call(_settings(), "x", {}, "s")
    assert decision == "block"
    assert "governance_unavailable" in detail["reason"]
