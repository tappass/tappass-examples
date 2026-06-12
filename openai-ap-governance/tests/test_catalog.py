from apdemo.catalog import get_vendor, get_asset, VENDORS


def test_vendor_has_synthetic_iban():
    v = get_vendor("V-1001")
    assert v["name"] == "Globex Supplies"
    # Synthetic IBAN — NOT a real account. Present so PII redaction is visible.
    assert v["iban"].startswith("DE")


def test_unknown_vendor_returns_none():
    assert get_vendor("V-9999") is None


def test_asset_classification():
    a = get_asset("vendor_bank_accounts")
    assert a["classification"] == "restricted"
