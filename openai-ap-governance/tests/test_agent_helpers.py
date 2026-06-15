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
