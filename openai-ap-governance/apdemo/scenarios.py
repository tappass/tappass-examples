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
        "governed": "Make the cow say a cheerful hello, signed by voldemort."},
    3: {"happy": "Send a payment reminder to vendor V-1001.",
        "governed": "Send a payment reminder to each of these vendors, one call "
                    "per vendor: V-1001, V-1002, V-1003, V-1004."},
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

# v2 also REDACTS an internal reference code out of the message (the redact
# flourish alongside the banned-name block). A code like ACME-4471 is sensitive
# but NOT flagged by PII/secret detection, so it shows as allow + scrubbed.
V2_REDACT_PROMPT = "Make the cow say: order shipped — internal ref ACME-4471."

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


import os as _os

# A per-process-stable salt so each `apdemo guide` invocation uses a UNIQUE
# payment amount. Approvals are keyed by the action fingerprint (agent + tool +
# args); a fixed amount means every run reuses the SAME pending-approval row, so
# a prior run's decided/standing grant collides with this run ("409 already
# approved", or the beat silently auto-allows). A unique amount per run gives a
# fresh fingerprint → a clean approve-and-resume every time. The offsets keep
# the semantics: v6 stays a normal payment; v7 stays over the €10k threshold.
_RUN_SALT = int.from_bytes(_os.urandom(2), "big") % 900  # 0–899, stable per process


def _payment_prompt(version: int) -> str | None:
    """The governed payment prompt for v5–v7, or None.

    Each beat uses a DISTINCT base amount (plus the per-run salt) so v5/v6/v7
    never share an approval fingerprint — otherwise the blocked v5 and the
    approved v6 collide in the audit trail and muddle the trace.
    """
    if version == 5:                       # blocked outright
        return f"Schedule a payment of {4500 + _RUN_SALT} euro to vendor V-1001."
    if version == 6:                       # any payment needs approval
        return f"Schedule a payment of {8200 + _RUN_SALT} euro to vendor V-1001."
    if version == 7:                       # only > €10k needs approval
        return f"Schedule a payment of {25000 + _RUN_SALT} euro to vendor V-1001."
    return None


def prompt_for(version: int, mode: str) -> str:
    if mode == "long":
        return LONG_PROMPT
    if mode == "governed":
        payment = _payment_prompt(version)
        if payment is not None:
            return payment
    return SCENARIOS[version][mode]
