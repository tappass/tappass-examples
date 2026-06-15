from apdemo.verdicts import VerdictHandler, classify_error


def test_classify_block():
    label, reason = classify_error("governance block: the cow may not say that (step=cond_1)")
    assert label == "BLOCKED" and "cow may not say" in reason


def test_classify_approval():
    label, _ = classify_error("governance block: approval required")
    assert label == "APPROVAL REQUIRED"


def test_classify_rate_limit():
    label, reason = classify_error("governance block: rate_limited")
    assert label == "BLOCKED" and "rate" in reason.lower()


def test_handler_renders_governed(capsys):
    h = VerdictHandler(governed=True)
    h.on_tool_start({"name": "cowsay"}, '{"message":"hi"}')
    h.on_tool_end("…cow…", name="cowsay")
    out = capsys.readouterr().out
    assert "GOVERNED" in out and "cowsay" in out


def test_handler_renders_block(capsys):
    h = VerdictHandler(governed=True)
    h.on_tool_start({"name": "cowsay"}, '{"message":"voldemort"}')
    h.on_tool_error(Exception("governance block: the cow may not say that"), name="cowsay")
    out = capsys.readouterr().out
    assert "BLOCKED" in out
