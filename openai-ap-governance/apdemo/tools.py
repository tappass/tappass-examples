"""AP agent tools: pure implementations + OpenAI function schemas + version gating."""
from __future__ import annotations

import ast
import operator as _op
from typing import Callable

from . import catalog

# ── safe arithmetic for `calculate` ──────────────────────────────
_OPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
    ast.Div: _op.truediv, ast.Pow: _op.pow, ast.USub: _op.neg,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def _calculate(args: dict) -> dict:
    tree = ast.parse(str(args["expression"]), mode="eval")
    return {"result": _eval(tree.body)}


def _lookup_vendor(args: dict) -> dict:
    v = catalog.get_vendor(args["vendor_id"])
    return v or {"error": "vendor_not_found"}


def _compute_invoice_total(args: dict) -> dict:
    subtotal = round(sum(float(li["amount"]) for li in args["line_items"]), 2)
    tax = round(subtotal * float(args.get("tax_rate", 0.0)), 2)
    return {"subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)}


def _schedule_payment(args: dict) -> dict:
    return {"status": "scheduled", "vendor_id": args["vendor_id"],
            "amount": float(args["amount"])}


def _update_vendor_bank_details(args: dict) -> dict:
    return {"status": "updated", "vendor_id": args["vendor_id"], "iban": args["iban"]}


def _set_asset_classification(args: dict) -> dict:
    return {"status": "classified", "asset_id": args["asset_id"],
            "classification": args["classification"]}


def _propose_schema_change(args: dict) -> dict:
    return {"status": "proposed", "asset_id": args["asset_id"], "change": args["change"]}


# ── registry: name -> (min_ver, schema, impl) ────────────────────
def _schema(name: str, desc: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


_REGISTRY: dict[str, tuple[int, dict, Callable[[dict], dict]]] = {
    "calculate": (0, _schema(
        "calculate", "Evaluate an arithmetic expression.",
        {"expression": {"type": "string"}}, ["expression"]), _calculate),
    "lookup_vendor": (2, _schema(
        "lookup_vendor", "Look up a vendor record by id (includes bank details).",
        {"vendor_id": {"type": "string"}}, ["vendor_id"]), _lookup_vendor),
    "compute_invoice_total": (2, _schema(
        "compute_invoice_total", "Sum invoice line items and apply a tax rate.",
        {"line_items": {"type": "array", "items": {"type": "object"}},
         "tax_rate": {"type": "number"}}, ["line_items"]), _compute_invoice_total),
    "schedule_payment": (3, _schema(
        "schedule_payment", "Schedule a payment to a vendor for an amount.",
        {"vendor_id": {"type": "string"}, "amount": {"type": "number"}},
        ["vendor_id", "amount"]), _schedule_payment),
    "update_vendor_bank_details": (5, _schema(
        "update_vendor_bank_details", "Change a vendor's bank account (IBAN).",
        {"vendor_id": {"type": "string"}, "iban": {"type": "string"}},
        ["vendor_id", "iban"]), _update_vendor_bank_details),
    "set_asset_classification": (6, _schema(
        "set_asset_classification", "Set the data classification of a catalog asset.",
        {"asset_id": {"type": "string"},
         "classification": {"type": "string",
                            "enum": catalog.CLASSIFICATION_ORDER}},
        ["asset_id", "classification"]), _set_asset_classification),
    "propose_schema_change": (6, _schema(
        "propose_schema_change", "Propose a schema change to a catalog asset.",
        {"asset_id": {"type": "string"}, "change": {"type": "string"}},
        ["asset_id", "change"]), _propose_schema_change),
}


def tools_for_version(n: int) -> tuple[list[dict], dict[str, Callable[[dict], dict]]]:
    schemas, impls = [], {}
    for name, (min_ver, schema, impl) in _REGISTRY.items():
        if min_ver <= n:
            schemas.append(schema)
            impls[name] = impl
    return schemas, impls


def dispatch(name: str, args: dict) -> dict:
    entry = _REGISTRY.get(name)
    if entry is None:
        return {"error": f"unknown tool: {name}"}
    return entry[2](args)
