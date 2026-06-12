import os
from apdemo.config import Settings


def test_defaults(monkeypatch):
    for k in ["TAPPASS_URL", "TAPPASS_PAT", "TAPPASS_AGENT_KEY", "TAPPASS_MODEL"]:
        monkeypatch.delenv(k, raising=False)
    s = Settings.load()
    assert s.url == "https://app.tappass.ai"
    assert s.model == "gpt-4o-mini"
    assert s.pat is None
