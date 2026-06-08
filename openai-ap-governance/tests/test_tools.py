from apdemo.tools import tools_for_version, dispatch


def test_v0_has_only_calculator():
    schemas, _impls = tools_for_version(0)
    names = {s["function"]["name"] for s in schemas}
    assert names == {"calculate"}


def test_v3_unlocks_schedule_payment():
    schemas, _ = tools_for_version(3)
    names = {s["function"]["name"] for s in schemas}
    assert {"calculate", "lookup_vendor", "compute_invoice_total", "schedule_payment"} <= names


def test_v6_unlocks_catalog_tools():
    schemas, _ = tools_for_version(6)
    names = {s["function"]["name"] for s in schemas}
    assert {"set_asset_classification", "propose_schema_change"} <= names


def test_calculate_executes():
    assert dispatch("calculate", {"expression": "40 + 2"}) == {"result": 42}


def test_compute_invoice_total_with_tax():
    out = dispatch("compute_invoice_total",
                   {"line_items": [{"amount": 100.0}, {"amount": 50.0}], "tax_rate": 0.1})
    assert out == {"subtotal": 150.0, "tax": 15.0, "total": 165.0}


def test_lookup_vendor_returns_iban():
    out = dispatch("lookup_vendor", {"vendor_id": "V-1001"})
    assert out["iban"].startswith("DE")
