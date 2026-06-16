from types import SimpleNamespace
import apdemo.agent as A


def _settings(**kw):
    base = dict(url="https://app.tappass.ai", pat="pat", agent_key="ak", agent_uuid="ag",
                agent_id="ap-demo-agent", policy_id="pid", org="org", model="gpt-4o-mini",
                openai_api_key="sk", owner_email="demo@example.com")
    base.update(kw)
    return SimpleNamespace(require_agent_key=lambda: base["agent_key"], **base)


def test_v0_tools_are_ungoverned(monkeypatch):
    captured = {}
    monkeypatch.setattr(A.tappass, "govern", lambda tools, **kw: captured.setdefault("called", True) or tools)
    tools = A.build_tools(0, _settings(), "sess")
    assert "called" not in captured           # v0 never wraps
    assert {t.name for t in tools} == {"cowsay", "calculator"}


def test_v1_wraps_with_enforce(monkeypatch):
    seen = {}
    def fake_govern(tools, **kw):
        seen.update(kw); return tools
    monkeypatch.setattr(A.tappass, "govern", fake_govern)
    A.build_tools(1, _settings(), "sess-123")
    assert seen["mode"] == "enforce"
    assert seen["agent_id"] == "ap-demo-agent"
    assert seen["session_id"] == "sess-123"


def test_model_routing(monkeypatch):
    made = {}
    monkeypatch.setattr(A, "ChatOpenAI", lambda **kw: made.update(kw) or SimpleNamespace(**kw))
    A.build_model(0, _settings(), "s")
    assert made["base_url"].startswith("https://api.openai.com")
    made.clear()
    A.build_model(1, _settings(), "s")
    assert made["base_url"] == "https://app.tappass.ai/v1"


# ── approve-and-resume orchestration (_drive) ────────────────────────────────
from tappass._govern_call import ApprovalPending, GovernanceBlocked  # noqa: E402


def _pending(rid="req-1"):
    return ApprovalPending(request_id=rid, reason="payment needs sign-off")


class _FakeAgent:
    def __init__(self, raises):
        self.raises = list(raises)   # exception or None, per invoke
        self.invokes = 0

    def invoke(self, messages, config):
        self.invokes += 1
        exc = self.raises[min(self.invokes - 1, len(self.raises) - 1)]
        if exc is not None:
            raise exc
        return {"messages": [SimpleNamespace(content="done")]}


def _handler(name="schedule_payment", args=None):
    h = A.VerdictHandler(governed=True)
    h.last_tool = (name, args or {"vendor_id": "V-1001", "amount": 100})
    return h


def test_drive_grants_exact_action_then_resumes():
    # ADR 0016: needs_approval surfaces as ApprovalPending; approve + re-run.
    agent = _FakeAgent([_pending(), None])
    grant = {}
    def approve_cb(name, args, detail):
        grant["call"] = (name, args); return True
    A._drive(agent, "pay", {}, approve_cb, _handler())
    assert agent.invokes == 2                       # halted, then resumed
    assert grant["call"] == ("schedule_payment", {"vendor_id": "V-1001", "amount": 100})


def test_drive_halts_when_reviewer_declines():
    agent = _FakeAgent([_pending()])
    A._drive(agent, "pay", {}, lambda *a: False, _handler())
    assert agent.invokes == 1                        # no resume on decline


def test_drive_does_not_grant_on_a_hard_block():
    # A hard denial (GovernanceBlocked) is NOT an approval — never grant, never resume.
    agent = _FakeAgent([GovernanceBlocked("blocked_tool: schedule_payment")])
    granted = {"n": 0}
    def approve_cb(*a):
        granted["n"] += 1; return True
    A._drive(agent, "pay", {}, approve_cb, _handler())
    assert agent.invokes == 1 and granted["n"] == 0  # denial → no grant
