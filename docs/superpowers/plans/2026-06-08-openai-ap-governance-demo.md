# Incremental AP-Agent Governance Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single reusable Python package (`tappass-examples/openai-ap-governance/`) that demonstrates an Accounts-Payable OpenAI agent growing from ungoverned (v0) through six escalating TapPass governance postures (v1–v6), with a PAT-driven script that provisions one policy with six versions activated one after another against the live `app.tappass.ai`.

**Architecture:** One version-gated package. `apdemo run --version N` runs the agent with only the tools unlocked at version N; v0 talks directly to OpenAI, v1–v6 route through the TapPass gateway (`base_url` swap). `apdemo setup` uses a PAT to create a demo agent + one policy with six draft versions; `apdemo activate --version N` publishes version N and assigns it to the agent. Governance is enforced server-side by the gateway against the active policy version's compiled Rego.

**Tech Stack:** Python 3.10+, `openai`, `httpx`, `python-dotenv`, `pytest`. Control-plane API at `https://app.tappass.ai/api/*` (PAT auth), data-plane gateway at `https://app.tappass.ai/v1/*` (agent key auth).

**Grounded API facts (verified against core repo `/Users/jensbontinck/tappass/tappass`):**
- `POST /api/agents/onboard` body: `{agent_id, owner_email, org_id?, project_id?, description?, framework?, ...}` → response includes `agent_uuid` and `api_key.api_key` (a `tp_dev_*` key, shown once).
- `GET /api/me/access` → `{projects:[{project_id, role, name}], teams:[{team_id,...}], is_org_admin}`. Org slug comes from `GET /api/me` → `org_id` (e.g. `tappass-6ab653`).
- `POST /api/v2/policies` body: `{org_id (slug), name, description}` → `{id (policy_id), ...}`.
- `POST /api/v2/policies/{policy_id}/versions` body: `{rules:[{kind, ordinal, payload}], change_note}` → `{version_no, status, ...}`.
- `PUT /api/v2/policies/{policy_id}/versions/{v}/rules` — edit a draft's rules in place.
- `POST /api/v2/policies/{policy_id}/versions/{v}/publish` — activate.
- `POST /api/v2/policies/{policy_id}/versions/{v}/pull-back` — re-activate an older version (sequential activation supported).
- `POST /api/v2/policies/{policy_id}/assignments` body: `{scope_type:"agent", scope_id: <agent_uuid>, effective_until?}`.
- Rule kinds + payloads (from `tappass/kernel/policy/templates.py`): `BlockTool {tools:[...]}`, `AllowTool {tools:[...]}`, `BlockPII {scope:"output"|"input"}`, `BlockSecrets {}`, `PerToolRateLimit {tool, max, window_seconds}`, `RequireApproval {tools:[...], tier, reason}` (or `{matchers:[{tool,arg,pattern}], tier, reason}`), `Conditional {when, then}`.
- `Conditional` (from `tappass/kernel/policy/conditional.py`): `when` is a tree — leaf `{signal:"<dotted.lowercase.path>", op, value}`, or `{all:[...]}`, or `{any:[...]}`. Ops include `eq, neq, in, not_in, gt, gte, lt, lte, match, count_gt, ...`. `then` = `{action, reason?, tier?, model?, tool?, arg?, pattern?}`, action ∈ `{block, allow, require_approval, route_to_model, redact}`. A `signal` of `request.tool` reads `input.request.tool`.

**Three facts that need a live trace (verification tasks 8–9, not guesses):**
1. Whether tool-call arguments are exposed as typed input signals (e.g. `input.request.args.amount`) for gateway calls — affects v5 numeric threshold and v6 classification floor. Fallback if not: `RequireApproval {tools:[schedule_payment]}` (blunt) for v5's payment rule, and a `BlockTool`/matcher-regex approach for v6.
2. The exact v2 redaction surface (tool-result vs prompt) — `RedactToolArg` (regex on a tool arg) vs `BlockPII {scope:"output"}`.
3. Whether org `tappass-6ab653` has an upstream LLM provider key for the gateway, or the demo must supply `OPENAI_API_KEY` as BYOK; and the model name.

**Credential rule:** the PAT and the minted agent key live ONLY in a gitignored `.env`. Never write either into any committed file, scenario, README, or test fixture.

---

## File Structure

```
tappass-examples/openai-ap-governance/
  apdemo/
    __init__.py        # version constant, exports
    config.py          # env loading + Settings dataclass
    catalog.py         # in-memory fake vendor/invoice/asset dataset
    tools.py           # AP tool implementations + OpenAI schemas + min_ver tags
    rules.py           # pure rule-set builders: rules_for_version(n) -> list[dict]
    provision.py       # control-plane HTTP client (org/agent/policy/versions/assign/teardown)
    agent.py           # OpenAI agentic loop; client selection by version; outcome rendering
    scenarios.py       # per-version canned prompts (happy + governed)
    cli.py             # argparse: setup | activate | run | status | teardown
  tests/
    test_catalog.py
    test_tools.py
    test_rules.py
    test_provision_bodies.py
    test_agent_helpers.py
  README.md            # v0->v6 walkthrough + talk track
  .env.example
  .gitignore           # .env
  pyproject.toml
```

Each file has one responsibility. `rules.py` is pure (no network) so the per-version rule JSON is unit-testable. `provision.py` holds only HTTP/orchestration. `tools.py`/`catalog.py` are pure Python. `agent.py` keeps only the loop + client wiring.

---

## Task 0: Scaffold the package

**Files:**
- Create: `openai-ap-governance/pyproject.toml`
- Create: `openai-ap-governance/.gitignore`
- Create: `openai-ap-governance/.env.example`
- Create: `openai-ap-governance/apdemo/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "openai-ap-governance"
version = "0.1.0"
description = "Incremental AP-agent governance demo for TapPass"
requires-python = ">=3.10"
dependencies = [
    "openai>=1.40",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
apdemo = "apdemo.cli:main"

[tool.setuptools.packages.find]
include = ["apdemo*"]
```

- [ ] **Step 2: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`** (placeholders only — no real secrets)

```bash
# Control plane (PAT). Get yours from app.tappass.ai > Settings > Access Tokens.
TAPPASS_URL=https://app.tappass.ai
TAPPASS_PAT=tp_pat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Written by `apdemo setup` (the minted agent data-plane key). Do not fill by hand.
TAPPASS_AGENT_KEY=
TAPPASS_AGENT_UUID=
TAPPASS_POLICY_ID=

# Model the agent asks for (must be served by the gateway / BYOK).
TAPPASS_MODEL=gpt-4o-mini

# Used by v0 (direct-to-OpenAI baseline) and as gateway BYOK if the org has no key.
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Owner email recorded on the demo agent.
DEMO_OWNER_EMAIL=you@example.com
```

- [ ] **Step 4: Create `apdemo/__init__.py`**

```python
"""Incremental AP-agent governance demo for TapPass."""

MIN_VERSION = 0
MAX_VERSION = 6

__all__ = ["MIN_VERSION", "MAX_VERSION"]
```

- [ ] **Step 5: Commit**

```bash
cd /Users/jensbontinck/tappass/tappass-examples
git add openai-ap-governance/pyproject.toml openai-ap-governance/.gitignore openai-ap-governance/.env.example openai-ap-governance/apdemo/__init__.py
git commit -m "feat(ap-demo): scaffold openai-ap-governance package"
```

---

## Task 1: `config.py` — environment loading

**Files:**
- Create: `openai-ap-governance/apdemo/config.py`
- Test: `openai-ap-governance/tests/test_config.py` *(optional smoke; config is thin — see Step 3)*

- [ ] **Step 1: Write `config.py`**

```python
"""Environment-backed settings. No secrets in source."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads .env if present; real values never committed


@dataclass(frozen=True)
class Settings:
    url: str
    pat: str | None
    agent_key: str | None
    agent_uuid: str | None
    policy_id: str | None
    model: str
    openai_api_key: str | None
    owner_email: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            url=os.getenv("TAPPASS_URL", "https://app.tappass.ai").rstrip("/"),
            pat=os.getenv("TAPPASS_PAT") or None,
            agent_key=os.getenv("TAPPASS_AGENT_KEY") or None,
            agent_uuid=os.getenv("TAPPASS_AGENT_UUID") or None,
            policy_id=os.getenv("TAPPASS_POLICY_ID") or None,
            model=os.getenv("TAPPASS_MODEL", "gpt-4o-mini"),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            owner_email=os.getenv("DEMO_OWNER_EMAIL", "demo@example.com"),
        )

    def require_pat(self) -> str:
        if not self.pat:
            raise SystemExit("TAPPASS_PAT is not set. Add it to .env (control-plane PAT).")
        return self.pat

    def require_agent_key(self) -> str:
        if not self.agent_key:
            raise SystemExit("TAPPASS_AGENT_KEY is not set. Run `apdemo setup` first.")
        return self.agent_key
```

- [ ] **Step 2: Smoke-test config loads from env**

```python
# tests/test_config.py
import os
from apdemo.config import Settings


def test_defaults(monkeypatch):
    for k in ["TAPPASS_URL", "TAPPASS_PAT", "TAPPASS_AGENT_KEY", "TAPPASS_MODEL"]:
        monkeypatch.delenv(k, raising=False)
    s = Settings.load()
    assert s.url == "https://app.tappass.ai"
    assert s.model == "gpt-4o-mini"
    assert s.pat is None
```

- [ ] **Step 3: Run the test**

Run: `cd openai-ap-governance && python -m pytest tests/test_config.py -v`
Expected: PASS. (If `.env` in the repo root leaks `TAPPASS_URL`, the monkeypatch.delenv keeps the test hermetic — `load()` reads `os.getenv` after deletion.)

- [ ] **Step 4: Commit**

```bash
git add openai-ap-governance/apdemo/config.py openai-ap-governance/tests/test_config.py
git commit -m "feat(ap-demo): env-backed Settings"
```

---

## Task 2: `catalog.py` — fake AP dataset

**Files:**
- Create: `openai-ap-governance/apdemo/catalog.py`
- Test: `openai-ap-governance/tests/test_catalog.py`

The dataset deliberately contains a synthetic IBAN (documented as fake) so v2 redaction is observable, and assets with classifications so v6 has something to protect.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalog.py
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: apdemo.catalog`.

- [ ] **Step 3: Write `catalog.py`**

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_catalog.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add openai-ap-governance/apdemo/catalog.py openai-ap-governance/tests/test_catalog.py
git commit -m "feat(ap-demo): in-memory fake AP/catalog dataset"
```

---

## Task 3: `tools.py` — AP tools, schemas, version gating

**Files:**
- Create: `openai-ap-governance/apdemo/tools.py`
- Test: `openai-ap-governance/tests/test_tools.py`

Each tool is `(min_ver, openai_schema, impl)`. `tools_for_version(n)` returns the schemas + a name→impl dispatch for tools with `min_ver <= n`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools.py
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: apdemo.tools`.

- [ ] **Step 3: Write `tools.py`**

```python
"""AP agent tools: pure implementations + OpenAI function schemas + version gating."""
from __future__ import annotations

import ast
import operator as _op
from typing import Any, Callable

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
    return {"subtotal": subtotal, "tax": round(tax, 2), "total": round(subtotal + tax, 2)}


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
                            "enum": ["public", "internal", "confidential", "restricted"]}},
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
    return _REGISTRY[name][2](args)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_tools.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add openai-ap-governance/apdemo/tools.py openai-ap-governance/tests/test_tools.py
git commit -m "feat(ap-demo): AP tools with version gating + schemas"
```

---

## Task 4: `rules.py` — per-version rule-set builders (pure)

**Files:**
- Create: `openai-ap-governance/apdemo/rules.py`
- Test: `openai-ap-governance/tests/test_rules.py`

`rules_for_version(n)` returns the list of `{kind, ordinal, payload}` dicts for policy version n (n=1..6). This is the heart of the governance story and is fully unit-tested with no network.

> NOTE: v5 and v6 use `Conditional` rules that read `input.request.args.*`. If verification Task 8 finds tool-arg signals are NOT populated, swap the two flagged rules for the documented fallbacks (see comments). Keep this function the single place rules are defined.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rules.py
from apdemo.rules import rules_for_version


def test_v1_is_allow_all():
    assert rules_for_version(1) == []


def test_v2_has_secrets_and_pii():
    kinds = [r["kind"] for r in rules_for_version(2)]
    assert "BlockSecrets" in kinds
    assert "BlockPII" in kinds


def test_v3_gates_payment_write():
    rs = rules_for_version(3)
    allow = next(r for r in rs if r["kind"] == "AllowTool")
    assert "schedule_payment" not in allow["payload"]["tools"]
    assert "lookup_vendor" in allow["payload"]["tools"]


def test_v4_requires_approval_on_payment():
    rs = rules_for_version(4)
    appr = next(r for r in rs if r["kind"] == "RequireApproval")
    assert "schedule_payment" in appr["payload"]["tools"]
    assert appr["payload"]["tier"] in ("authenticated", "elevated")


def test_v5_conditional_bank_change_and_threshold():
    rs = rules_for_version(5)
    conds = [r for r in rs if r["kind"] == "Conditional"]
    # one rule keys on the bank-detail tool, one on the payment amount
    signals = [_leaf_signals(c["payload"]["when"]) for c in conds]
    flat = {s for group in signals for s in group}
    assert "request.tool" in flat


def test_v6_blocks_weak_classification():
    rs = rules_for_version(6)
    cond = next(r for r in rs if r["kind"] == "Conditional"
                and r["payload"]["then"]["action"] == "block")
    assert cond["payload"]["then"]["action"] == "block"


def _leaf_signals(node):
    if "signal" in node:
        return [node["signal"]]
    key = "all" if "all" in node else "any"
    out = []
    for child in node.get(key, []):
        out += _leaf_signals(child)
    return out
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: apdemo.rules`.

- [ ] **Step 3: Write `rules.py`**

```python
"""Per-version policy rule-sets. Pure functions; no network.

Each rule is {"kind": str, "ordinal": int, "payload": dict} matching the
TapPass v2 RuleSpec. Versions are cumulative in *intent*, but each version is
the COMPLETE rule-set that policy version N publishes (the server replaces the
active rule-set on publish).

Rule kinds + payload fields are grounded in tappass/kernel/policy/templates.py
and conditional.py.
"""
from __future__ import annotations

# Tools the agent is allowed to call once enforcement turns on (v3+). Reads only.
_READ_TOOLS = ["calculate", "lookup_vendor", "compute_invoice_total"]

_PAYMENT_THRESHOLD = 10000  # EUR; payments above this need approval (v5)


def rules_for_version(n: int) -> list[dict]:
    if n <= 1:
        return []  # v1 = allow-all (observability only)

    rules: list[dict] = []

    # v2+: secret scan + PII handling on model-bound content.
    rules.append({"kind": "BlockSecrets", "ordinal": 0, "payload": {}})
    rules.append({"kind": "BlockPII", "ordinal": 1, "payload": {"scope": "output"}})
    if n == 2:
        return rules

    # v3+: tool-call enforcement. Allow-list the read tools; the payment WRITE
    # is intentionally absent, so it is blocked until a later version permits it
    # under approval.
    allowed = list(_READ_TOOLS)
    if n >= 4:
        # From v4 on, schedule_payment is permitted but gated by approval below.
        allowed.append("schedule_payment")
    if n >= 5:
        allowed.append("update_vendor_bank_details")
    if n >= 6:
        allowed += ["set_asset_classification", "propose_schema_change"]
    rules.append({"kind": "AllowTool", "ordinal": 2, "payload": {"tools": allowed}})
    if n == 3:
        return rules

    # v4: blunt human-in-the-loop approval on every payment.
    if n == 4:
        rules.append({"kind": "RequireApproval", "ordinal": 3, "payload": {
            "tools": ["schedule_payment"],
            "tier": "authenticated",
            "reason": "AP payment requires reviewer approval",
        }})
        return rules

    # v5: context-aware. Bank-detail changes ALWAYS need elevated approval
    # (classic AP-fraud vector); payments only need approval over the threshold.
    if n >= 5:
        rules.append({"kind": "Conditional", "ordinal": 3, "payload": {
            "when": {"signal": "request.tool", "op": "eq",
                     "value": "update_vendor_bank_details"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "Vendor bank-detail change requires elevated approval"},
        }})
        # FALLBACK (if input.request.args.amount is not a signal — see Task 8):
        #   replace the rule below with
        #   {"kind":"RequireApproval","ordinal":4,
        #    "payload":{"tools":["schedule_payment"],"tier":"authenticated",
        #               "reason":"AP payment requires approval"}}
        rules.append({"kind": "Conditional", "ordinal": 4, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "schedule_payment"},
                {"signal": "request.args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD},
            ]},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": f"Payment over EUR {_PAYMENT_THRESHOLD} requires approval"},
        }})
    if n == 5:
        return rules

    # v6: same kernel now governs catalog edits. The agent may never WEAKEN a
    # classification (floor rule: block any attempt to set it below confidential),
    # and any schema change needs elevated approval.
    if n >= 6:
        rules.append({"kind": "Conditional", "ordinal": 5, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.args.classification", "op": "in",
                 "value": ["public", "internal"]},
            ]},
            "then": {"action": "block",
                     "reason": "agent may not weaken a data classification"},
        }})
        rules.append({"kind": "Conditional", "ordinal": 6, "payload": {
            "when": {"signal": "request.tool", "op": "eq", "value": "propose_schema_change"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "catalog schema change requires elevated approval"},
        }})
    return rules


def change_note(n: int) -> str:
    notes = {
        1: "v1: allow-all — observability only",
        2: "v2: secret scan + PII redaction on output",
        3: "v3: tool-call enforcement (gate the payment write)",
        4: "v4: human approval on payments",
        5: "v5: context-aware — bank changes + over-threshold payments need approval",
        6: "v6: govern the catalog — block classification weakening; approve schema changes",
    }
    return notes[n]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_rules.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add openai-ap-governance/apdemo/rules.py openai-ap-governance/tests/test_rules.py
git commit -m "feat(ap-demo): per-version policy rule-set builders"
```

---

## Task 5: `provision.py` — control-plane client

**Files:**
- Create: `openai-ap-governance/apdemo/provision.py`
- Test: `openai-ap-governance/tests/test_provision_bodies.py`

Holds the HTTP calls. Request-body construction is split into pure helpers so they can be asserted without a network.

- [ ] **Step 1: Write the failing test (pure body builders)**

```python
# tests/test_provision_bodies.py
from apdemo.provision import (
    onboard_body, policy_body, version_body, assignment_body,
)


def test_onboard_body():
    b = onboard_body(agent_id="ap-demo-agent", org_id="tappass-6ab653",
                     owner_email="you@example.com")
    assert b["agent_id"] == "ap-demo-agent"
    assert b["org_id"] == "tappass-6ab653"
    assert b["owner_email"] == "you@example.com"
    assert b["framework"] == "custom"


def test_policy_body():
    b = policy_body(org_id="tappass-6ab653", name="AP Demo Policy")
    assert b == {"org_id": "tappass-6ab653", "name": "AP Demo Policy",
                 "description": "Incremental AP-agent governance demo"}


def test_version_body_carries_rules_and_note():
    b = version_body(3)
    assert b["change_note"].startswith("v3")
    assert any(r["kind"] == "AllowTool" for r in b["rules"])


def test_assignment_body_keys_on_agent_uuid():
    b = assignment_body(agent_uuid="ag_ABC123")
    assert b == {"scope_type": "agent", "scope_id": "ag_ABC123"}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_provision_bodies.py -v`
Expected: FAIL with `ModuleNotFoundError: apdemo.provision`.

- [ ] **Step 3: Write `provision.py`**

```python
"""PAT-driven control-plane client + pure request-body builders.

Endpoints verified against core repo:
  GET  /api/me                                          -> {org_id (slug), ...}
  POST /api/agents/onboard                              -> {agent_uuid, api_key:{api_key}}
  POST /api/v2/policies                                 -> {id}
  POST /api/v2/policies/{id}/versions                   -> {version_no}
  POST /api/v2/policies/{id}/versions/{v}/publish
  POST /api/v2/policies/{id}/versions/{v}/pull-back
  POST /api/v2/policies/{id}/assignments
"""
from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .rules import change_note, rules_for_version


# ── pure body builders (unit-tested) ─────────────────────────────
def onboard_body(*, agent_id: str, org_id: str, owner_email: str) -> dict:
    return {
        "agent_id": agent_id,
        "org_id": org_id,
        "owner_email": owner_email,
        "description": "Incremental AP-agent governance demo",
        "framework": "custom",
        "intended_use": "Accounts Payable assistant (demo)",
    }


def policy_body(*, org_id: str, name: str) -> dict:
    return {"org_id": org_id, "name": name,
            "description": "Incremental AP-agent governance demo"}


def version_body(n: int) -> dict:
    return {"rules": rules_for_version(n), "change_note": change_note(n)}


def assignment_body(*, agent_uuid: str) -> dict:
    return {"scope_type": "agent", "scope_id": agent_uuid}


# ── HTTP client ──────────────────────────────────────────────────
class ControlPlane:
    def __init__(self, settings: Settings):
        self.s = settings
        self._http = httpx.Client(
            base_url=settings.url,
            headers={"Authorization": f"Bearer {settings.require_pat()}"},
            timeout=30,
        )

    def _post(self, path: str, body: dict | None = None) -> dict:
        r = self._http.post(path, json=body or {})
        if r.status_code >= 400:
            raise SystemExit(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content else {}

    def _get(self, path: str) -> dict:
        r = self._http.get(path)
        if r.status_code >= 400:
            raise SystemExit(f"GET {path} -> {r.status_code}: {r.text}")
        return r.json()

    # — org —
    def org_slug(self) -> str:
        return self._get("/api/me")["org_id"]

    # — agent —
    def onboard_agent(self, agent_id: str) -> dict:
        org = self.org_slug()
        resp = self._post("/api/agents/onboard", onboard_body(
            agent_id=agent_id, org_id=org, owner_email=self.s.owner_email))
        return {"agent_uuid": resp["agent_uuid"],
                "agent_key": resp["api_key"]["api_key"]}

    # — policy —
    def create_policy(self, name: str) -> str:
        org = self.org_slug()
        return self._post("/api/v2/policies", policy_body(org_id=org, name=name))["id"]

    def create_version(self, policy_id: str, n: int) -> int:
        resp = self._post(f"/api/v2/policies/{policy_id}/versions", version_body(n))
        return resp["version_no"]

    def publish(self, policy_id: str, version_no: int) -> dict:
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/publish")

    def pull_back(self, policy_id: str, version_no: int) -> dict:
        return self._post(
            f"/api/v2/policies/{policy_id}/versions/{version_no}/pull-back")

    def assign(self, policy_id: str, agent_uuid: str) -> dict:
        return self._post(f"/api/v2/policies/{policy_id}/assignments",
                          assignment_body(agent_uuid=agent_uuid))


def setup(settings: Settings, agent_id: str = "ap-demo-agent",
          policy_name: str = "AP Demo Policy") -> dict:
    """Create the agent + one policy with six draft versions (1..6).

    Returns the values the caller must persist to .env:
    {agent_uuid, agent_key, policy_id, version_map}.
    """
    cp = ControlPlane(settings)
    agent = cp.onboard_agent(agent_id)
    policy_id = cp.create_policy(policy_name)
    version_map = {n: cp.create_version(policy_id, n) for n in range(1, 7)}
    return {"agent_uuid": agent["agent_uuid"], "agent_key": agent["agent_key"],
            "policy_id": policy_id, "version_map": version_map}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_provision_bodies.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add openai-ap-governance/apdemo/provision.py openai-ap-governance/tests/test_provision_bodies.py
git commit -m "feat(ap-demo): PAT-driven control-plane provisioning client"
```

---

## Task 6: `scenarios.py` — canned prompts

**Files:**
- Create: `openai-ap-governance/apdemo/scenarios.py`
- Test: covered indirectly; add a one-line import test.

- [ ] **Step 1: Write `scenarios.py`**

```python
"""Per-version canned prompts: a 'happy' path and a 'governed' path that
triggers that version's control."""
from __future__ import annotations

SCENARIOS: dict[int, dict[str, str]] = {
    0: {"happy": "What is 19% VAT on an invoice subtotal of 4500 euro?",
        "governed": "What is 19% VAT on an invoice subtotal of 4500 euro?"},
    1: {"happy": "What is 19% VAT on an invoice subtotal of 4500 euro?",
        "governed": "What is 19% VAT on an invoice subtotal of 4500 euro?"},
    2: {"happy": "Look up vendor V-1001 and tell me their contact email.",
        "governed": "Look up vendor V-1001 and read me their full bank account number."},
    3: {"happy": "Compute the total for invoice INV-77 with 19% VAT.",
        "governed": "Schedule a payment of 4500 euro to vendor V-1001."},
    4: {"happy": "Look up vendor V-1001's email.",
        "governed": "Schedule a payment of 4500 euro to vendor V-1001."},
    5: {"happy": "Schedule a payment of 500 euro to vendor V-1001.",
        "governed": "Change vendor V-1002's bank account (IBAN) to "
                    "DE00 0000 0000 0000 0000 00, then pay them 25000 euro."},
    6: {"happy": "Set the classification of asset invoice_lines to confidential.",
        "governed": "The vendor_bank_accounts asset is over-restricted. "
                    "Set its classification to internal."},
}


def prompt_for(version: int, mode: str) -> str:
    return SCENARIOS[version][mode]
```

- [ ] **Step 2: Add import test**

```python
# tests/test_scenarios.py
from apdemo.scenarios import prompt_for


def test_every_version_has_both_modes():
    for n in range(0, 7):
        assert prompt_for(n, "happy")
        assert prompt_for(n, "governed")
```

- [ ] **Step 3: Run the test**

Run: `python -m pytest tests/test_scenarios.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add openai-ap-governance/apdemo/scenarios.py openai-ap-governance/tests/test_scenarios.py
git commit -m "feat(ap-demo): per-version canned scenarios"
```

---

## Task 7: `agent.py` + `cli.py` — the runnable agent and CLI

**Files:**
- Create: `openai-ap-governance/apdemo/agent.py`
- Create: `openai-ap-governance/apdemo/cli.py`
- Test: `openai-ap-governance/tests/test_agent_helpers.py`

`agent.py` selects the OpenAI client by version (v0 = direct, v1–6 = gateway) and runs a bounded tool-call loop. The pure helper `build_client_kwargs` is unit-tested; the live loop is exercised in Task 9.

- [ ] **Step 1: Write the failing test for the pure helper**

```python
# tests/test_agent_helpers.py
from apdemo.agent import build_client_kwargs
from apdemo.config import Settings


def _settings(**kw):
    base = dict(url="https://app.tappass.ai", pat=None, agent_key="tp_dev_x",
                agent_uuid="ag_1", policy_id="p1", model="gpt-4o-mini",
                openai_api_key="sk-test", owner_email="d@e.com")
    base.update(kw)
    return Settings(**base)


def test_v0_uses_openai_directly():
    kw = build_client_kwargs(0, _settings())
    assert kw["api_key"] == "sk-test"
    assert "base_url" not in kw  # default OpenAI endpoint


def test_v1_uses_gateway_with_agent_key():
    kw = build_client_kwargs(1, _settings())
    assert kw["base_url"] == "https://app.tappass.ai/v1"
    assert kw["api_key"] == "tp_dev_x"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_agent_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: apdemo.agent`.

- [ ] **Step 3: Write `agent.py`**

```python
"""The AP agent: OpenAI agentic loop, governed via the TapPass gateway (v1+)."""
from __future__ import annotations

import json

from openai import OpenAI

from .config import Settings
from .tools import dispatch, tools_for_version


def build_client_kwargs(version: int, s: Settings) -> dict:
    """v0 talks to OpenAI directly; v1+ route through the TapPass gateway."""
    if version == 0:
        if not s.openai_api_key:
            raise SystemExit("v0 needs OPENAI_API_KEY (direct OpenAI).")
        return {"api_key": s.openai_api_key}
    return {"base_url": f"{s.url}/v1", "api_key": s.require_agent_key()}


def run(version: int, prompt: str, s: Settings, max_steps: int = 6) -> None:
    client = OpenAI(**build_client_kwargs(version, s))
    schemas, _ = tools_for_version(version)
    messages = [
        {"role": "system", "content":
         "You are an Accounts Payable assistant. Use tools when needed."},
        {"role": "user", "content": prompt},
    ]
    for _ in range(max_steps):
        try:
            resp = client.chat.completions.create(
                model=s.model, messages=messages,
                tools=schemas or None)
        except Exception as e:  # gateway block / approval surface as HTTP errors
            print(f"\n[GOVERNANCE] call stopped: {type(e).__name__}: {e}")
            return
        msg = resp.choices[0].message
        if not msg.tool_calls:
            print(f"\n[ASSISTANT] {msg.content}")
            return
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print(f"[TOOL] {tc.function.name}({args})")
            result = dispatch(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result)})
    print("\n[done: step budget reached]")
```

> NOTE for Task 9: the exact way the gateway signals block/redaction/approval on
> the `/v1/chat/completions` path (HTTP status, error body, or a mutated message)
> is confirmed live. Adjust the `except` branch / add an approval-poll on
> `/v1/me/approvals/{id}/wait` once the real shape is known.

- [ ] **Step 4: Run the helper test to verify it passes**

Run: `python -m pytest tests/test_agent_helpers.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Write `cli.py`**

```python
"""apdemo CLI: setup | activate | run | status | teardown."""
from __future__ import annotations

import argparse
import sys

from . import agent as agent_mod
from .config import Settings
from .provision import ControlPlane, setup as provision_setup
from .scenarios import prompt_for


def _env_dump(values: dict) -> str:
    return "\n".join(f"{k}={v}" for k, v in values.items())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="apdemo")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create agent + policy with 6 versions")

    a = sub.add_parser("activate", help="publish + assign policy version N (1..6)")
    a.add_argument("--version", type=int, required=True, choices=range(1, 7))

    r = sub.add_parser("run", help="run the agent at version N (0..6)")
    r.add_argument("--version", type=int, required=True, choices=range(0, 7))
    r.add_argument("--scenario", choices=["happy", "governed"], default="happy")
    r.add_argument("--prompt", default=None)

    sub.add_parser("status", help="show active policy + assignment")
    sub.add_parser("teardown", help="remove the demo agent + policy")

    args = p.parse_args(argv)
    s = Settings.load()

    if args.cmd == "setup":
        out = provision_setup(s)
        print("# Add these to openai-ap-governance/.env:")
        print(_env_dump({
            "TAPPASS_AGENT_KEY": out["agent_key"],
            "TAPPASS_AGENT_UUID": out["agent_uuid"],
            "TAPPASS_POLICY_ID": out["policy_id"],
        }))
        print(f"# version_map: {out['version_map']}")
        return 0

    if args.cmd == "activate":
        cp = ControlPlane(s)
        if not s.policy_id or not s.agent_uuid:
            raise SystemExit("Run `apdemo setup` and fill .env first.")
        cp.publish(s.policy_id, args.version)
        cp.assign(s.policy_id, s.agent_uuid)
        print(f"Activated + assigned policy version {args.version}.")
        return 0

    if args.cmd == "run":
        prompt = args.prompt or prompt_for(args.version, args.scenario)
        print(f"# v{args.version} [{args.scenario}] prompt: {prompt}")
        agent_mod.run(args.version, prompt, s)
        return 0

    if args.cmd == "status":
        print(f"url={s.url} agent_uuid={s.agent_uuid} policy_id={s.policy_id}")
        return 0

    if args.cmd == "teardown":
        print("Teardown: delete the agent + policy in the dashboard, or extend "
              "ControlPlane with delete calls (see Task 10).")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Commit**

```bash
git add openai-ap-governance/apdemo/agent.py openai-ap-governance/apdemo/cli.py openai-ap-governance/tests/test_agent_helpers.py
git commit -m "feat(ap-demo): runnable agent loop + apdemo CLI"
```

---

## Task 8: Live verification of the three open facts (read-mostly)

This task resolves the three flagged uncertainties against `app.tappass.ai` using the PAT in `.env`. It creates the agent + policy (real writes), then probes shapes. No customer-facing run yet.

- [ ] **Step 1: Install + run the full unit suite**

```bash
cd openai-ap-governance
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q
```
Expected: all unit tests PASS.

- [ ] **Step 2: Run setup against the live env**

```bash
python -m apdemo.cli setup
```
Expected: prints `TAPPASS_AGENT_KEY`, `TAPPASS_AGENT_UUID`, `TAPPASS_POLICY_ID`, and `version_map={1:1,...,6:6}`. Paste the three values into `.env`. If `onboard` 409s (agent exists from a prior run), change `agent_id` or tear down first.

- [ ] **Step 3: Confirm LLM availability (open fact #3)**

Activate v1 (allow-all) and run the happy path:
```bash
python -m apdemo.cli activate --version 1
python -m apdemo.cli run --version 1 --scenario happy
```
Expected: an assistant answer. If the gateway returns a "no provider key"/model error, the org lacks BYOK — set `OPENAI_API_KEY` in `.env` (the gateway uses it as BYOK) or pick a `TAPPASS_MODEL` the platform serves, and re-run. Record the working model in `.env.example` comments.

- [ ] **Step 4: Confirm tool-arg signals (open fact #1)**

Activate v5 and run the governed payment prompt:
```bash
python -m apdemo.cli activate --version 5
python -m apdemo.cli run --version 5 --scenario governed
```
Expected: the over-threshold payment escalates to approval. If instead it is allowed (the `request.args.amount` signal isn't populated), apply the documented fallback in `rules.py` (blunt `RequireApproval` on `schedule_payment`), edit the draft via `ControlPlane`/the PUT-rules route, re-publish v5, and note the limitation in the README.

- [ ] **Step 5: Confirm v2 redaction surface (open fact #2)**

```bash
python -m apdemo.cli activate --version 2
python -m apdemo.cli run --version 2 --scenario governed
```
Inspect the session trace in the dashboard for the agent. Confirm the IBAN is redacted. If `BlockPII {scope:"output"}` blocks rather than redacts (or doesn't fire on tool-result content), switch v2's PII rule to `RedactToolArg {matchers:[{tool:"lookup_vendor", arg:"...", pattern:"<IBAN regex>"}]}` in `rules.py`, re-publish v2, and re-verify.

- [ ] **Step 6: Commit any rule adjustments**

```bash
git add openai-ap-governance/apdemo/rules.py openai-ap-governance/.env.example
git commit -m "fix(ap-demo): align rules with live gateway signal/redaction shapes"
```

---

## Task 9: Full dress rehearsal (v0 → v6) + README

**Files:**
- Create: `openai-ap-governance/README.md`

- [ ] **Step 1: Run the ungoverned baseline**

```bash
python -m apdemo.cli run --version 0 --scenario happy
```
Expected: an answer, with NO TapPass audit entry (it went straight to OpenAI). This is the "before" state.

- [ ] **Step 2: Walk every governed version**

For each N in 1..6: `activate --version N`, then `run --version N --scenario happy` and `run --version N --scenario governed`. Confirm the expected outcome per the ladder:
- v1: both allowed; audit entries appear.
- v2: governed prompt's IBAN redacted in the trace.
- v3: governed `schedule_payment` blocked.
- v4: governed payment escalates → approve in dashboard → resumes.
- v5: bank-change escalates (elevated); 25k payment escalates; a 500-euro payment (happy) is allowed.
- v6: setting `vendor_bank_accounts` to `internal` is blocked; `propose_schema_change` escalates.

Record any mismatch as a bug and fix `rules.py`, re-publishing the affected version.

- [ ] **Step 3: Write `README.md`** — the v0→v6 walkthrough + talk track. Document: the one-line v0→v1 change (`base_url`), the `apdemo setup/activate/run` commands, what to point at in the dashboard for each version, and the synthetic-data disclaimer. Do NOT include the PAT or agent key.

- [ ] **Step 4: Final unit-suite run + commit**

```bash
python -m pytest -q
git add openai-ap-governance/README.md
git commit -m "docs(ap-demo): v0->v6 walkthrough and talk track"
```

---

## Task 10 (optional): teardown / re-runnability

**Files:**
- Modify: `openai-ap-governance/apdemo/provision.py`
- Modify: `openai-ap-governance/apdemo/cli.py`

- [ ] **Step 1: Confirm delete endpoints** — agent delete is `DELETE /api/agents/{agent_uuid}` (verified in `registry.py:307`). Find the policy delete/retire route in `policies_v2_writes.py` (or retire by publishing an empty version). Add `ControlPlane.delete_agent(uuid)` and `ControlPlane.delete_policy(id)`.

- [ ] **Step 2: Wire `teardown` in `cli.py`** to call both, guarded by a `--yes` flag.

- [ ] **Step 3: Commit**

```bash
git add openai-ap-governance/apdemo/provision.py openai-ap-governance/apdemo/cli.py
git commit -m "feat(ap-demo): teardown for re-runnable demos"
```

---

## Self-Review

**Spec coverage:**
- v0 ungoverned baseline → Task 7 (`build_client_kwargs` v0 path), Task 9 Step 1. ✓
- v1–v6 governance ladder → `rules.py` (Task 4), provisioning (Task 5), activation (Task 7 CLI), verified (Tasks 8–9). ✓
- One policy, six versions, sequential activation → `provision.setup` creates 6 versions; `activate` publishes + assigns; pull-back available. ✓
- Mediated gateway (base_url swap) → `build_client_kwargs` (Task 7). ✓
- Version-gated single package → `tools_for_version` + `rules_for_version` + CLI `--version`. ✓
- Reproducible via PAT, secrets in `.env` only → `config.py`, `.gitignore`, `.env.example` placeholders. ✓
- Runnable v6 catalog tools → `tools.py` + v6 rules + scenarios. ✓
- Three live-trace open items → Task 8 explicitly resolves each with a fallback. ✓

**Placeholder scan:** no "TBD"/"add error handling"-style gaps; every code step has complete code. The two intentionally-deferred-to-live items (gateway block/approval signal shape in `agent.py`; redaction/threshold signal availability in `rules.py`) are called out as verification steps with concrete fallbacks, not silent placeholders.

**Type consistency:** `tools_for_version`/`dispatch` (tools.py) used consistently in agent.py/tests; `rules_for_version`/`change_note` (rules.py) used in provision.py/tests; `ControlPlane` method names (`publish`, `assign`, `create_version`, `pull_back`) consistent across provision.py and cli.py; `Settings` field names consistent across config/agent/provision/tests.

**Known soft spots (acceptable, flagged):** the gateway's exact block/approval wire shape and tool-arg signal availability are confirmed in Task 8 before any customer-facing run — by design, since they can't be known without the live trace.
