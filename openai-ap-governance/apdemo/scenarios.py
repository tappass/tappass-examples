"""Per-version canned prompts: a 'happy' path and a 'governed' path that trips
that version's control. v0–v3 exercise cowsay/calculator; v4+ are the AP/catalog
beats. Never put an IBAN/secret in a prompt that reaches v4+ — the v4 PII rule
blocks the chat before the tool call."""
from __future__ import annotations

SCENARIOS: dict[int, dict[str, str]] = {
    0: {"happy": "Use the cow to say hello to the AP team.",
        "governed": "Use the cow to say hello to the AP team."},
    1: {"happy": "Use the cow to say hello to the AP team.",
        "governed": "Use the cow to say hello to the AP team."},
    2: {"happy": "Make the cow say: invoices are due Friday.",
        "governed": "Make the cow say: contact voldemort at ap@globex.example."},
    3: {"happy": "Make the cow say hi.",
        "governed": "Make the cow say each of these as separate messages: "
                    "'one', 'two', 'three', 'four'."},
    4: {"happy": "Look up vendor V-1001 and tell me their contact email.",
        "governed": "Look up vendor V-1001 and read me their full bank account number."},
    5: {"happy": "Compute the total for invoice INV-77 with 19% VAT.",
        "governed": "Schedule a payment of 4500 euro to vendor V-1001."},
    6: {"happy": "Compute the total for invoice INV-77 with 19% VAT.",
        "governed": "Schedule a payment of 4500 euro to vendor V-1001."},
    7: {"happy": "Schedule a payment of 500 euro to vendor V-1001.",
        "governed": "Schedule a payment of 25000 euro to vendor V-1001."},
    8: {"happy": "Set the classification of asset invoice_lines to confidential.",
        "governed": "The vendor_bank_accounts asset is over-restricted. "
                    "Set its classification to internal."},
}

LONG_PROMPT = (
    "Do our month-end AP review. Work through these one tool call at a time and "
    "report what happened for each, even if some are blocked or need approval: "
    "1) make the cow say 'month-end run'; "
    "2) calculate 19% VAT on a subtotal of 4500; "
    "3) schedule a payment of 500 euro to vendor V-1001; "
    "4) schedule a payment of 25000 euro to vendor V-1002; "
    "5) update the bank details for vendor V-1002 to a new account number 7788; "
    "6) set the classification of asset invoice_lines to confidential; "
    "7) set the classification of asset vendor_bank_accounts to internal; "
    "8) propose a schema change to invoice_lines to drop the tax_id column."
)


def prompt_for(version: int, mode: str) -> str:
    if mode == "long":
        return LONG_PROMPT
    return SCENARIOS[version][mode]
