"""AP agent tools as LangChain @tool objects + version gating.

cowsay/calculator are Collibra's starter tools (v0). The AP + catalog tools layer
on at later versions. tools_for_version(n) returns the raw @tool objects; the agent
wraps them with tappass.govern() for enforcement. Tool ARG NAMES are the contract the
policy reads via request.tool_args.* — do not rename without updating apdemo/rules.py.
"""
from __future__ import annotations

import operator as _op

from langchain_core.tools import tool

from . import catalog

_OPS = {"+": _op.add, "-": _op.sub, "*": _op.mul, "/": _op.truediv}


@tool
def cowsay(message: str) -> str:
    """Display a message as ASCII art of a cow saying it.

    Args:
        message: The text the cow should say.
    """
    border = "-" * (len(message) + 2)
    return (f" {border}\n< {message} >\n {border}\n        \\   ^__^\n"
            f"         \\  (oo)\\_______\n            (__)\\       )\\/\\\n"
            f"                ||----w |\n                ||     ||")


@tool
def calculator(a: float, b: float, op: str) -> str:
    """Calculate the result of an arithmetic operation on two numbers.

    Args:
        a: First number.
        b: Second number.
        op: Operation to perform: "+", "-", "*", or "/".
    """
    if op not in _OPS:
        return f"Unknown operation '{op}'. Use one of: {', '.join(_OPS)}"
    if op == "/" and b == 0:
        return "Error: division by zero"
    return str(_OPS[op](float(a), float(b)))


#: A small "thinking" pause so each governed send_reminder call is recorded in
#: the durable audit trail before the next one is governed. The v3 rate-limit
#: producer counts govern_allow records from that trail; without a gap a fast
#: burst undercounts (the writes lag) and the 4th call slips through. ~2.5s lets
#: each call settle so the limit reliably fires on the 4th. send_reminder is the
#: ONLY tool the rate limit targets, and it's used ONLY in v3 — so its window is
#: never polluted by other beats (cowsay, used in v0–v2, is unaffected).
_REMINDER_SETTLE_SECONDS = 2.5


@tool
def send_reminder(vendor_id: str) -> str:
    """Send a payment-reminder notification to a vendor.

    Args:
        vendor_id: The vendor to remind.
    """
    import time
    time.sleep(_REMINDER_SETTLE_SECONDS)
    return str({"status": "reminder_sent", "vendor_id": vendor_id})


@tool
def lookup_vendor(vendor_id: str) -> str:
    """Look up a vendor record by id (includes bank details)."""
    v = catalog.get_vendor(vendor_id)
    return str(v or {"error": "vendor_not_found"})


@tool
def compute_invoice_total(line_items: list, tax_rate: float = 0.0) -> str:
    """Sum invoice line items and apply a tax rate."""
    subtotal = round(sum(float(li["amount"]) for li in line_items), 2)
    tax = round(subtotal * float(tax_rate), 2)
    return str({"subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)})


@tool
def schedule_payment(vendor_id: str, amount: float) -> str:
    """Schedule a payment to a vendor for an amount."""
    return str({"status": "scheduled", "vendor_id": vendor_id, "amount": float(amount)})


@tool
def update_vendor_bank_details(vendor_id: str, iban: str) -> str:
    """Change a vendor's bank account (IBAN)."""
    return str({"status": "updated", "vendor_id": vendor_id, "iban": iban})


@tool
def export_asset(asset_id: str, destination: str) -> str:
    """Export a catalog asset's data to a destination (file share, external system)."""
    return str({"status": "exported", "asset_id": asset_id, "destination": destination})


@tool
def set_asset_classification(asset_id: str, classification: str) -> str:
    """Set the data classification of a catalog asset."""
    return str({"status": "classified", "asset_id": asset_id, "classification": classification})


@tool
def propose_schema_change(asset_id: str, change: str) -> str:
    """Propose a schema change to a catalog asset."""
    return str({"status": "proposed", "asset_id": asset_id, "change": change})


# name -> (min_version, tool object)
_REGISTRY: dict[str, tuple[int, object]] = {
    "cowsay": (0, cowsay),
    "calculator": (0, calculator),
    "send_reminder": (3, send_reminder),
    "lookup_vendor": (4, lookup_vendor),
    "compute_invoice_total": (4, compute_invoice_total),
    "schedule_payment": (5, schedule_payment),
    "update_vendor_bank_details": (7, update_vendor_bank_details),
    "export_asset": (9, export_asset),
    "set_asset_classification": (8, set_asset_classification),
    "propose_schema_change": (8, propose_schema_change),
}


def tools_for_version(n: int) -> list:
    """FRESH @tool objects unlocked at version n (additive).

    Returns deep copies, never the module-level singletons. ``tappass.govern``
    wraps a tool IN-PLACE (setattr on its hook attr), so handing it the shared
    object every beat would STACK govern wrappers — by v7 a payment tool carries
    v5+v6+v7 wrappers and one invocation fires three govern calls, each tagged
    with its beat's session_id (the cross-session trace bleed). A fresh copy per
    build means each beat governs its own tool exactly once.
    """
    import copy
    return [copy.deepcopy(t) for _name, (min_ver, t) in _REGISTRY.items() if min_ver <= n]


def dispatch(name: str, args: dict) -> str:
    """Invoke a tool's underlying function directly (for unit tests / non-agent use)."""
    entry = _REGISTRY.get(name)
    if entry is None:
        return f"unknown tool: {name}"
    return entry[1].invoke(args)
