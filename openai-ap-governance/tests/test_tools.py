from apdemo import tools as T


def test_cowsay_and_calculator_are_v0():
    names = {t.name for t in T.tools_for_version(0)}
    assert names == {"cowsay", "calculator"}


def test_cowsay_renders_message():
    out = T.dispatch("cowsay", {"message": "hi"})
    assert "hi" in out and "^__^" in out  # the cow


def test_calculator_basic_ops():
    assert T.dispatch("calculator", {"a": 6, "b": 7, "op": "*"}) == "42.0"
    assert T.dispatch("calculator", {"a": 1, "b": 0, "op": "/"}).startswith("Error")


def test_tool_gating_is_additive():
    assert {t.name for t in T.tools_for_version(4)} >= {"cowsay", "calculator",
                                                        "lookup_vendor", "compute_invoice_total"}
    assert "schedule_payment" not in {t.name for t in T.tools_for_version(4)}
    assert "schedule_payment" in {t.name for t in T.tools_for_version(5)}
    assert "update_vendor_bank_details" in {t.name for t in T.tools_for_version(7)}
    assert "set_asset_classification" in {t.name for t in T.tools_for_version(8)}


def test_tools_are_langchain_tools():
    for t in T.tools_for_version(8):
        assert hasattr(t, "name") and hasattr(t, "invoke")  # StructuredTool surface
