from apdemo.agent import build_client_kwargs
from apdemo.config import Settings


def _settings(**kw):
    base = dict(url="https://app.tappass.ai", pat=None, agent_key="tp_dev_x",
                agent_uuid="ag_1", policy_id="p1", model="gpt-4o-mini",
                openai_api_key="sk-test", owner_email="d@e.com",
                version_map={})
    base.update(kw)
    return Settings(**base)


def test_v0_uses_openai_directly():
    kw = build_client_kwargs(0, _settings())
    assert kw["api_key"] == "sk-test"
    assert "base_url" not in kw  # default OpenAI endpoint


def test_v1_uses_gateway_with_agent_key():
    kw = build_client_kwargs(1, _settings())
    assert kw["base_url"] == "https://app.tappass.ai/v1"
    assert kw["api_key"] == "tp_dev_x"
