"""In-memory fake AP dataset. All identifiers are synthetic.

The IBANs here are NOT real bank accounts — they exist so the PII-redaction
demo (v2) has something to redact.
"""
from __future__ import annotations

VENDORS: dict[str, dict] = {
    "V-1001": {
        "id": "V-1001",
        "name": "Globex Supplies",
        "email": "ap@globex.example",
        "iban": "DE89 3704 0044 0532 0130 00",  # synthetic
        "bank_changed_days_ago": 400,
    },
    "V-1002": {
        "id": "V-1002",
        "name": "Initech Components",
        "email": "billing@initech.example",
        "iban": "FR14 2004 1010 0505 0001 3M02 606",  # synthetic
        "bank_changed_days_ago": 2,
    },
}

INVOICES: dict[str, dict] = {
    "INV-77": {"id": "INV-77", "vendor_id": "V-1001",
               "line_items": [{"desc": "widgets", "amount": 4200.0},
                              {"desc": "freight", "amount": 300.0}]},
}

# Data-catalog assets the v6 agent can touch (Collibra-style).
ASSETS: dict[str, dict] = {
    "vendor_bank_accounts": {"id": "vendor_bank_accounts", "classification": "restricted"},
    "invoice_lines": {"id": "invoice_lines", "classification": "internal"},
}

# Classification ordering, weakest -> strongest. Used by the demo's narration
# and (optionally) by client-side guards; the server-side rule is authoritative.
CLASSIFICATION_ORDER = ["public", "internal", "confidential", "restricted"]


def get_vendor(vendor_id: str) -> dict | None:
    return VENDORS.get(vendor_id)


def get_invoice(invoice_id: str) -> dict | None:
    return INVOICES.get(invoice_id)


def get_asset(asset_id: str) -> dict | None:
    return ASSETS.get(asset_id)
