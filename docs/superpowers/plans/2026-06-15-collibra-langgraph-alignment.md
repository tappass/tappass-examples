# Collibra-Aligned LangGraph AP-Agent Governance Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-plumb the `apdemo` package so its agent matches Collibra's exact LangGraph + `tappass.govern(mode="enforce")` shape (seeded with his `cowsay`/`calculator` tools), open the governance ladder on those tools (arg-content block+redact, then audit-trail rate-limit), and make the approval beats a real escalate→human-approves→resume cycle that renders clearly in the audit + session trace.

**Architecture:** One version-gated package. `--version N` selects both the tool surface and the active policy version. The agent's two governance touch-points are Collibra's two lines: `ChatOpenAI(base_url=gateway)` (governs the LLM call) and `tappass.govern(tools, mode="enforce")` (governs each tool call). Approvals use `origin/main`'s approval-as-fact flow: a `require_approval` rule holds the call, a human approves (dashboard or `apdemo approve` → `POST /v1/govern/approve`), and the identical re-submitted call is allowed by the kernel's `ApprovalProducer`.

**Tech Stack:** Python 3.10+, `langchain` / `langgraph` / `langchain-openai`, the `tappass` SDK (`tappass.govern`), `httpx`, `pytest`. TapPass control-plane API on `app.tappass.ai`.

**Spec:** `docs/superpowers/specs/2026-06-15-collibra-langgraph-alignment-design.md`

**Working dir for all paths below:** `ap-governance-wt/openai-ap-governance/`

---

## Task 1: Live spike — resolve the approval response shape (gates Task 8)

This is a **spike**, not TDD. It records two facts that the approval task and the rule task depend on. Do it first; write findings into `LIVE-FINDINGS.md`.

**Files:**
- Modify: `LIVE-FINDINGS.md` (append a dated "2026-06-15 alignment spike" section)

- [ ] **Step 1: Confirm a venv with the SDK + deps is live**

Run:
```bash
cd ap-governance-wt/openai-ap-governance
. .venv/bin/activate 2>/dev/null || python -m venv .venv && . .venv/bin/activate
pip install -e . >/dev/null
pip install -e ../../tappass-sdk >/dev/null   # the local SDK (tappass.govern)
python -c "import tappass, langchain, langgraph, langchain_openai; print('ok')"
```
Expected: `ok` (if langchain/langgraph aren't installed yet, do Task 2 first, then return).

- [ ] **Step 2: Probe what `/v1/govern` returns for a require_approval TOOL_CALL**

With `.env` populated (`TAPPASS_PAT`, `TAPPASS_AGENT_KEY`, `TAPPASS_AGENT_UUID`, `TAPPASS_POLICY_ID`, `TAPPASS_ORG`), activate a version whose policy requires approval on `schedule_payment` (the current branch's v4), then POST a tool call directly and inspect the raw decision:

```bash
python - <<'PY'
import httpx, uuid
from apdemo.config import Settings
s = Settings.load()
behavior = {"type":"TOOL_CALL","agent_id":s.agent_id,"session_id":f"spike-{uuid.uuid4().hex[:8]}",
            "behavior_id":uuid.uuid4().hex,
            "payload":{"tool":"schedule_payment","args":{"vendor_id":"V-1001","amount":4500},"server":None}}
r = httpx.post(f"{s.url}/v1/govern", headers={"Authorization":f"Bearer {s.require_agent_key()}"}, json=behavior, timeout=30)
print(r.status_code); print(r.json())
PY
```
Record the `outcome` value: is it `"escalate"` (with an `approval.request_id`) or `"allow"` (with a `require_approval` entry under `obligations`)?

- [ ] **Step 3: Probe how the SDK's enforce wrapper reacts to that same call**

```bash
python - <<'PY'
import tappass
from apdemo.config import Settings
s = Settings.load()
def schedule_payment(vendor_id: str, amount: float) -> str:
    "Schedule a payment to a vendor for an amount."
    return "ran"
tools = tappass.govern([schedule_payment], url=s.url, api_key=s.require_agent_key(),
                       mode="enforce", agent_id=s.agent_id, session_id="spike-sdk")
gp = tools[0]
try:
    print("RESULT:", gp("V-1001", 4500))   # ran => SDK did NOT enforce approval; blocked => raised
except Exception as e:
    print("RAISED:", type(e).__name__, e)
PY
```
Interpretation:
- **RAISED `GovernanceBlocked`** → the server returns `escalate`/`block` and the SDK enforces. The approval beat works by the SDK long-polling `/v1/me/approvals/{id}/wait` (it blocks until a human decides). **→ Task 8 Path A.**
- **`RESULT: ran`** → the server returns `allow`+obligation and the SDK does **not** enforce approval on its own. **→ Task 8 Path B** (author the approval rule so it blocks-without-grant, and catch+grant+re-invoke).

- [ ] **Step 4: Confirm the two new rule kinds compile + fire live**

Temporarily publish a one-off version with the v2 `Conditional` banned-message block and a `PerToolRateLimit` on `cowsay`, then POST cowsay tool calls and confirm a block + a rate-limit block. (Reuse the direct-`/v1/govern` POST from Step 2 with `{"tool":"cowsay","args":{"message":"voldemort"}}` for the block, and 4 rapid `{"message":"hi"}` calls for the rate-limit.)
Record: does `request.tool_args.message` match fire? Does the 4th cowsay return a rate-limit block?

- [ ] **Step 5: Write findings to `LIVE-FINDINGS.md`**

Append a section `## 2026-06-15 alignment spike` capturing: the Step 2 outcome value, the Step 3 SDK behavior (Path A or B), and the Step 4 results. Commit.

```bash
git add LIVE-FINDINGS.md && git commit -m "spike: record approval response shape + v2/v3 rule liveness (Task 1)"
```

---

## Task 2: Add LangChain/LangGraph dependencies + bump version ceiling

**Files:**
- Modify: `pyproject.toml`
- Modify: `apdemo/__init__.py:4` (`MAX_VERSION = 6` → `8`)

- [ ] **Step 1: Add deps to `pyproject.toml`**

Replace the `dependencies` list:
```toml
dependencies = [
    "langchain>=0.3",
    "langgraph>=0.2",
    "langchain-openai>=0.2",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "tappass",
]
```
(Keep `[project.optional-dependencies] dev = ["pytest>=8.0"]` and the rest unchanged. `openai` arrives transitively via `langchain-openai`. The `tappass` SDK is installed editable in dev from `../../tappass-sdk`.)

- [ ] **Step 2: Raise the version ceiling**

In `apdemo/__init__.py`, change `MAX_VERSION = 6` to `MAX_VERSION = 8`.

- [ ] **Step 3: Install + import-check**

Run:
```bash
pip install -e . && pip install -e ../../tappass-sdk
python -c "import langchain, langgraph, langchain_openai, tappass; from apdemo import MAX_VERSION; assert MAX_VERSION==8; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**
```bash
git add pyproject.toml apdemo/__init__.py && git commit -m "build: add langchain/langgraph deps; raise MAX_VERSION to 8"
```

---

## Task 3: Convert tools to LangChain `@tool`, add `cowsay`

**Files:**
- Modify: `apdemo/tools.py` (full rewrite of the registry)
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_tools.py` with:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tools.py -q`
Expected: FAIL (import/attribute errors — registry not yet LangChain).

- [ ] **Step 3: Rewrite `apdemo/tools.py`**

```python
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
    "lookup_vendor": (4, lookup_vendor),
    "compute_invoice_total": (4, compute_invoice_total),
    "schedule_payment": (5, schedule_payment),
    "update_vendor_bank_details": (7, update_vendor_bank_details),
    "set_asset_classification": (8, set_asset_classification),
    "propose_schema_change": (8, propose_schema_change),
}


def tools_for_version(n: int) -> list:
    """The raw @tool objects unlocked at version n (additive)."""
    return [t for _name, (min_ver, t) in _REGISTRY.items() if min_ver <= n]


def dispatch(name: str, args: dict) -> str:
    """Invoke a tool's underlying function directly (for unit tests / non-agent use)."""
    entry = _REGISTRY.get(name)
    if entry is None:
        return f"unknown tool: {name}"
    return entry[1].invoke(args)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tools.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**
```bash
git add apdemo/tools.py tests/test_tools.py && git commit -m "feat: tools as LangChain @tool + cowsay seed; gate per new ladder"
```

---

## Task 4: Renumber rules to the 9-rung ladder + add v2/v3

**Files:**
- Modify: `apdemo/rules.py` (full rewrite)
- Test: `tests/test_rules.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_rules.py` with:
```python
from apdemo.rules import rules_for_version, change_note


def _kinds(n):
    return [r["kind"] for r in rules_for_version(n)]


def test_v0_v1_have_no_rules():
    assert rules_for_version(0) == [] and rules_for_version(1) == []


def test_v2_blocks_banned_message_and_redacts():
    rs = rules_for_version(2)
    cond = next(r for r in rs if r["kind"] == "Conditional")
    assert cond["payload"]["when"]["signal"] == "request.tool_args.message"
    assert cond["payload"]["then"]["action"] == "block"
    assert any(r["kind"] == "RedactToolArg" for r in rs)


def test_v3_adds_cowsay_rate_limit():
    rl = next(r for r in rules_for_version(3) if r["kind"] == "PerToolRateLimit")
    assert rl["payload"] == {"tool": "cowsay", "max": 3, "window_seconds": 120}
    # v2 rules still present (cumulative)
    assert "Conditional" in _kinds(3)


def test_v4_adds_output_pii_secrets():
    assert {"BlockSecrets", "BlockPII"} <= set(_kinds(4))


def test_v5_blocks_payment_write():
    assert any(r["kind"] == "BlockTool" and "schedule_payment" in r["payload"]["tools"]
               for r in rules_for_version(5))


def test_v6_requires_approval_on_payment_not_block():
    rs = rules_for_version(6)
    assert any(r["kind"] == "RequireApproval" for r in rs)
    assert not any(r["kind"] == "BlockTool" for r in rs)  # block superseded by approval


def test_v7_is_context_aware():
    conds = [r for r in rules_for_version(7) if r["kind"] == "Conditional"]
    actions = {r["payload"]["then"]["action"] for r in conds}
    assert "require_approval" in actions


def test_v8_governs_catalog():
    rs = rules_for_version(8)
    assert any(r["payload"]["then"].get("reason", "").startswith("agent may not weaken")
               for r in rs if r["kind"] == "Conditional")


def test_change_notes_cover_1_to_8():
    for n in range(1, 9):
        assert change_note(n)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_rules.py -q`
Expected: FAIL.

- [ ] **Step 3: Rewrite `apdemo/rules.py`**

```python
"""Per-version policy rule-sets. Pure functions; no network.

Each rule is {"kind": str, "ordinal": int, "payload": dict} (TapPass v2 RuleSpec).
rules_for_version(n) returns the COMPLETE rule-set version n publishes. Rules are
cumulative EXCEPT where a later version refines an earlier control (v5 blocks the
payment; v6 supersedes that with approval; v7 makes approval context-aware).

The kernel DEFAULTS TO ALLOW (ADR 0013) — enforcement is positive block/approval
rules, never allow-lists. Kinds + payloads grounded in kernel/policy/templates.py,
conditional.py, signal_catalog.py, producers/tool_rate.py and verified live (Task 1).
"""
from __future__ import annotations

# v2 — govern the cow's words
_BANNED_PATTERN = "(?i)(voldemort|enron)"            # banned names the cow may not say
_REDACT_PATTERN = r"[\w.+-]+@[\w-]+\.[\w.-]+"        # scrub emails out of the message
# v3 — frequency
_RATE_TOOL, _RATE_MAX, _RATE_WINDOW_S = "cowsay", 3, 120
# v7 — payment threshold
_PAYMENT_THRESHOLD = 10000  # EUR


def _cowsay_rules(o: int) -> list[dict]:
    return [
        {"kind": "Conditional", "ordinal": o, "payload": {
            "when": {"signal": "request.tool_args.message", "op": "match",
                     "value": _BANNED_PATTERN},
            "then": {"action": "block", "reason": "the cow may not say that"}}},
        {"kind": "RedactToolArg", "ordinal": o + 1, "payload": {
            "matchers": [{"tool": "cowsay", "arg": "message", "pattern": _REDACT_PATTERN}]}},
    ]


def _rate_rules(o: int) -> list[dict]:
    return [{"kind": "PerToolRateLimit", "ordinal": o, "payload": {
        "tool": _RATE_TOOL, "max": _RATE_MAX, "window_seconds": _RATE_WINDOW_S}}]


def _pii_rules(o: int) -> list[dict]:
    return [
        {"kind": "BlockSecrets", "ordinal": o, "payload": {}},
        {"kind": "BlockPII", "ordinal": o + 1, "payload": {"scope": "output"}},
    ]


def rules_for_version(n: int) -> list[dict]:
    if n <= 1:
        return []                                    # v1 = allow-all (observe only)

    rules: list[dict] = _cowsay_rules(0)             # v2: block banned word + redact
    if n == 2:
        return rules

    rules += _rate_rules(2)                           # v3: cowsay rate limit
    if n == 3:
        return rules

    rules += _pii_rules(3)                            # v4: output PII/secret block

    # v5: block the payment write. v6: supersede with approval. v7+: context-aware.
    if n == 5:
        rules.append({"kind": "BlockTool", "ordinal": 5,
                      "payload": {"tools": ["schedule_payment"]}})
    elif n == 6:
        rules.append({"kind": "RequireApproval", "ordinal": 5, "payload": {
            "tools": ["schedule_payment"], "tier": "authenticated",
            "reason": "AP payment requires reviewer approval"}})
    elif n >= 7:
        rules.append({"kind": "Conditional", "ordinal": 5, "payload": {
            "when": {"signal": "request.tool", "op": "eq",
                     "value": "update_vendor_bank_details"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "vendor bank-detail change requires elevated approval"}}})
        rules.append({"kind": "Conditional", "ordinal": 6, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "schedule_payment"},
                {"signal": "request.tool_args.amount", "op": "gt", "value": _PAYMENT_THRESHOLD}]},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": f"payment over EUR {_PAYMENT_THRESHOLD} requires approval"}}})

    if n >= 8:
        rules.append({"kind": "Conditional", "ordinal": 7, "payload": {
            "when": {"all": [
                {"signal": "request.tool", "op": "eq", "value": "set_asset_classification"},
                {"signal": "request.tool_args.classification", "op": "in",
                 "value": ["public", "internal"]}]},
            "then": {"action": "block", "reason": "agent may not weaken a data classification"}}})
        rules.append({"kind": "Conditional", "ordinal": 8, "payload": {
            "when": {"signal": "request.tool", "op": "eq", "value": "propose_schema_change"},
            "then": {"action": "require_approval", "tier": "elevated",
                     "reason": "catalog schema change requires elevated approval"}}})
    return rules


def change_note(n: int) -> str:
    notes = {
        1: "v1: allow-all — observability only",
        2: "v2: govern the cow's words — block a banned name, redact emails",
        3: "v3: rate-limit cowsay (3 calls / 2 min, from the audit trail)",
        4: "v4: secret scan + PII block on output",
        5: "v5: tool-call enforcement — block the payment write",
        6: "v6: human approval on payments (escalate → approve → resume)",
        7: "v7: context-aware — bank changes + over-threshold payments need approval",
        8: "v8: govern the catalog — block classification weakening; approve schema changes",
    }
    return notes[n]
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_rules.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**
```bash
git add apdemo/rules.py tests/test_rules.py && git commit -m "feat: 9-rung rule ladder; add cowsay content+rate rungs (v2/v3)"
```

---

## Task 5: Scenarios for v0–v8

**Files:**
- Modify: `apdemo/scenarios.py`
- Test: `tests/test_scenarios.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_scenarios.py` with:
```python
import re
from apdemo.scenarios import SCENARIOS, prompt_for, LONG_PROMPT


def test_every_version_has_happy_and_governed():
    for v in range(0, 9):
        assert "happy" in SCENARIOS[v] and "governed" in SCENARIOS[v]


def test_v2_governed_triggers_banned_word():
    assert re.search(r"(?i)voldemort|enron", SCENARIOS[2]["governed"])


def test_v3_governed_drives_repeated_cowsay():
    # the prompt must ask for several cowsay calls so the 4th trips the rate limit
    assert SCENARIOS[3]["governed"].lower().count("cow") >= 1


def test_long_prompt_present():
    assert "month-end" in LONG_PROMPT.lower()


def test_prompt_for_long_mode():
    assert prompt_for(6, "long") == LONG_PROMPT
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_scenarios.py -q`
Expected: FAIL (KeyError on versions 7/8 etc.).

- [ ] **Step 3: Rewrite `apdemo/scenarios.py`**

```python
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
        # banned name → blocked; also shows redaction when an email appears.
        "governed": "Make the cow say: contact voldemort at ap@globex.example."},
    3: {"happy": "Make the cow say hi.",
        # several cowsay calls in one turn → the 4th trips the 3/2min rate limit.
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_scenarios.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add apdemo/scenarios.py tests/test_scenarios.py && git commit -m "feat: v0-v8 scenarios; cowsay content+rate governed prompts"
```

---

## Task 6: Verdict callback handler

Governance now lives inside the SDK wrapper + LangGraph tool node. This LangChain callback renders the demo's signature verdict lines.

**Files:**
- Create: `apdemo/verdicts.py`
- Test: `tests/test_verdicts.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_verdicts.py`:
```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_verdicts.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `apdemo/verdicts.py`**

```python
"""LangChain callback handler that renders governance verdicts.

Governance decisions are made by tappass.govern() inside the tool wrapper; a block
surfaces as an exception on the tool. This handler is presentation-only — it never
makes a governance decision. It prints the demo's signature lines:
  [GOVERNED ✓ tool]   [BLOCKED reason]   [APPROVAL REQUIRED tier]
"""
from __future__ import annotations

from langchain_core.callbacks import BaseCallbackHandler

GREEN = "\033[32m"; RED = "\033[31m"; YELLOW = "\033[33m"; DIM = "\033[2m"; RESET = "\033[0m"


def classify_error(message: str) -> tuple[str, str]:
    """Map a GovernanceBlocked message to (label, human_reason)."""
    msg = message.split("governance block:", 1)[-1].strip() or message
    low = msg.lower()
    if "approval" in low:
        return "APPROVAL REQUIRED", msg
    if "rate" in low:
        return "BLOCKED", "rate limit exceeded"
    return "BLOCKED", msg


class VerdictHandler(BaseCallbackHandler):
    def __init__(self, governed: bool = True) -> None:
        self.governed = governed

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        name = (serialized or {}).get("name", "tool")
        print(f"{DIM}[TOOL] {name}({input_str}){RESET}")

    def on_tool_end(self, output, **kwargs) -> None:
        if not self.governed:
            return
        name = kwargs.get("name", "tool")
        print(f"{GREEN}[GOVERNED ✓ {name}]{RESET}")

    def on_tool_error(self, error: BaseException, **kwargs) -> None:
        label, reason = classify_error(str(error))
        color = YELLOW if label.startswith("APPROVAL") else RED
        print(f"{color}[{label}] {reason}{RESET}")
```

> **Step 3a (verify API):** confirm the installed `langchain_core` exposes `BaseCallbackHandler` at `langchain_core.callbacks` and that `on_tool_end`/`on_tool_error` receive a `name` kwarg in this version (`python -c "from langchain_core.callbacks import BaseCallbackHandler; import inspect; print(inspect.signature(BaseCallbackHandler.on_tool_end))"`). If `name` is not passed, track the current tool name from `on_tool_start` on `self` instead.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_verdicts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add apdemo/verdicts.py tests/test_verdicts.py && git commit -m "feat: VerdictHandler renders governance outcomes for LangGraph runs"
```

---

## Task 7: Rewrite `agent.py` around LangGraph + `tappass.govern`

**Files:**
- Modify: `apdemo/agent.py` (full rewrite; delete the OpenAI loop + hand-rolled govern)
- Test: `tests/test_agent_helpers.py`

- [ ] **Step 1: Write the failing tests** (pure — no network; assert wiring choices)

Replace `tests/test_agent_helpers.py` with:
```python
from types import SimpleNamespace
import apdemo.agent as A


def _settings(**kw):
    base = dict(url="https://app.tappass.ai", pat="pat", agent_key="ak", agent_uuid="ag",
                agent_id="ap-demo-agent", policy_id="pid", org="org", model="gpt-4o-mini",
                openai_api_key="sk", owner_email="demo@example.com")
    base.update(kw)
    return SimpleNamespace(require_agent_key=lambda: base["agent_key"], **base)


def test_v0_tools_are_ungoverned(monkeypatch):
    captured = {}
    monkeypatch.setattr(A.tappass, "govern", lambda tools, **kw: captured.setdefault("called", True) or tools)
    tools = A.build_tools(0, _settings(), "sess")
    assert "called" not in captured           # v0 never wraps
    assert {t.name for t in tools} == {"cowsay", "calculator"}


def test_v1_wraps_with_enforce(monkeypatch):
    seen = {}
    def fake_govern(tools, **kw):
        seen.update(kw); return tools
    monkeypatch.setattr(A.tappass, "govern", fake_govern)
    A.build_tools(1, _settings(), "sess-123")
    assert seen["mode"] == "enforce"
    assert seen["agent_id"] == "ap-demo-agent"
    assert seen["session_id"] == "sess-123"


def test_model_routing(monkeypatch):
    made = {}
    monkeypatch.setattr(A, "ChatOpenAI", lambda **kw: made.update(kw) or SimpleNamespace(**kw))
    A.build_model(0, _settings(), "s")
    assert made["base_url"].startswith("https://api.openai.com")
    made.clear()
    A.build_model(1, _settings(), "s")
    assert made["base_url"] == "https://app.tappass.ai/v1"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_agent_helpers.py -q`
Expected: FAIL.

- [ ] **Step 3: Rewrite `apdemo/agent.py`**

```python
"""The AP agent: a LangGraph agent governed via TapPass — Collibra's exact shape.

Two governance touch-points (v1+), both one line of customer code:
  * ChatOpenAI(base_url=<gateway>) routes the LLM call through TapPass (audit, cost,
    output PII/secret scan);
  * tappass.govern(tools, mode="enforce", ...) governs every tool call via /v1/govern
    before it runs — a block raises GovernanceBlocked; an approval drives the
    approve-and-resume flow (see run() / approve handling).

v0 talks to OpenAI directly with unwrapped tools — the ungoverned baseline.
"""
from __future__ import annotations

import uuid

import tappass
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from .config import Settings
from .tools import tools_for_version
from .verdicts import VerdictHandler

SYSTEM = ("You are an Accounts Payable assistant. Use tools when needed. "
          "Make ONE tool call at a time and report what happened for each.")


def build_model(version: int, s: Settings, session_id: str) -> ChatOpenAI:
    if version == 0:
        if not s.openai_api_key:
            raise SystemExit("v0 needs OPENAI_API_KEY (direct OpenAI).")
        return ChatOpenAI(model=s.model, base_url="https://api.openai.com/v1",
                          api_key=s.openai_api_key)
    return ChatOpenAI(model=s.model, base_url=f"{s.url}/v1",
                      api_key=s.require_agent_key(),
                      default_headers={"X-Session-Id": session_id})


def build_tools(version: int, s: Settings, session_id: str) -> list:
    raw = tools_for_version(version)
    if version == 0:
        return raw                                   # ungoverned baseline
    return tappass.govern(raw, url=s.url, api_key=s.require_agent_key(),
                          mode="enforce", agent_id=s.agent_id,
                          session_id=session_id, user_id=s.owner_email)


def build_agent(version: int, s: Settings, session_id: str):
    model = build_model(version, s, session_id)
    tools = build_tools(version, s, session_id)
    return create_agent(model, tools=tools, checkpointer=MemorySaver())


def run(version: int, prompt: str, s: Settings, max_steps: int = 6,
        approve_cb=None) -> str:
    """Run one agent interaction. Returns the session_id (for the trace URL).

    On the approval beats (v6–v8) the SDK enforce wrapper holds the gated tool
    until a human decides. ``approve_cb(name, args, detail) -> bool`` is the
    scripted reviewer hook (the guide wires it to POST /v1/govern/approve); when
    None, the demo relies on a human approving in the dashboard. See Task 8 for
    the resume mechanics chosen by the Task 1 spike.
    """
    session_id = f"apdemo-v{version}-{uuid.uuid4().hex[:8]}"
    print(f"# session: {session_id}")
    agent = build_agent(version, s, session_id)
    handler = VerdictHandler(governed=version >= 1)
    config = {"configurable": {"thread_id": session_id},
              "callbacks": [handler],
              "recursion_limit": max_steps * 2}
    _drive(agent, prompt, config, s, version, approve_cb)
    return session_id


def _drive(agent, prompt: str, config: dict, s: Settings, version: int,
           approve_cb) -> None:
    """Invoke the agent and print the final message. Approval-resume is layered
    on in Task 8 (kept as a separate seam so the spike result picks the path)."""
    result = agent.invoke({"messages": [("system", SYSTEM), ("user", prompt)]}, config)
    final = result["messages"][-1]
    content = getattr(final, "content", final)
    print(f"\n[ASSISTANT] {content}")
```

> **Step 3a (verify API):** confirm the import path `from langchain.agents import create_agent` and the `agent.invoke({"messages":[...]}, config)` / `result["messages"]` shape against the installed versions (mirror Collibra's snippet, which uses `create_agent` + `agent.astream({"messages": [("user", q)]}, config, stream_mode="messages")`). If `create_agent` is not at `langchain.agents` in the installed version, use the path Collibra's working snippet imports and note it in a comment.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_agent_helpers.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add apdemo/agent.py tests/test_agent_helpers.py && git commit -m "feat: LangGraph agent + tappass.govern(enforce); delete hand-rolled govern loop"
```

---

## Task 8: Wire real approve-and-resume (branch on Task 1)

Implement the path the Task 1 spike validated. Both are real code — keep the one that matches the spike; delete the other.

**Files:**
- Modify: `apdemo/agent.py` (`_drive` and a new `_approve_and_resume`)
- Modify: `LIVE-FINDINGS.md` (note which path shipped)

- [ ] **Step 1: Path A — server returns `escalate`, SDK long-polls (Task1 Step3 = RAISED)**

The SDK's `govern(mode="enforce")` long-polls `/v1/me/approvals/{id}/wait` internally (`wait=True`), so the gated tool simply **blocks until a human decides**. For the live (headline) demo, nothing extra is needed — the presenter approves in the dashboard and the agent resumes. For the **scripted** guide, approve out-of-band on a timer: run the agent in a worker thread and, if `approve_cb` is provided, grant immediately so the in-flight `/wait` resolves.

Replace `_drive` with:
```python
import threading

def _drive(agent, prompt, config, s, version, approve_cb):
    # Scripted approval: grant the known gated action right after kickoff so the
    # SDK's in-flight /wait long-poll resolves and the agent resumes. The live
    # path needs no callback — a human approves in the dashboard within the
    # SDK's wait window.
    if approve_cb and version >= 6:
        threading.Timer(2.0, lambda: _grant_pending(s, version, approve_cb)).start()
    result = agent.invoke({"messages": [("system", SYSTEM), ("user", prompt)]}, config)
    final = result["messages"][-1]
    print(f"\n[ASSISTANT] {getattr(final, 'content', final)}")


def _grant_pending(s, version, approve_cb):
    """Best-effort scripted grant: approve the version's expected gated action."""
    from .scenarios import EXPECTED_APPROVAL  # {version: (tool, args, detail)}
    spec = EXPECTED_APPROVAL.get(version)
    if spec:
        approve_cb(spec[0], spec[1], spec[2])
```
Add to `scenarios.py` an `EXPECTED_APPROVAL` map (the tool+args each governed prompt escalates), e.g. `{6: ("schedule_payment", {"vendor_id": "V-1001", "amount": 4500}, {"tier": "authenticated"}), 7: ("schedule_payment", {"vendor_id": "V-1001", "amount": 25000}, {"tier": "elevated"}), 8: ("propose_schema_change", {"asset_id": "invoice_lines", "change": "drop tax_id"}, {"tier": "elevated"})}`.

- [ ] **Step 1 (alt): Path B — SDK does NOT enforce approval (Task1 Step3 = ran)**

If the SDK ran the tool, author the v6–v8 approval rules to **block when not granted** (the approval-as-fact gate: `Conditional` with `when` including `{"signal": "subject.approval.granted", "op": "neq", "value": true}` → `action: block, reason: "approval required"`), so the SDK raises `GovernanceBlocked`. Then catch it at the run level, grant (dashboard or `approve_cb` → `/v1/govern/approve`), and re-invoke the agent on the same `thread_id` so the checkpointed run resubmits the identical call and the `ApprovalProducer` allows it:
```python
from tappass._govern_call import GovernanceBlocked

def _drive(agent, prompt, config, s, version, approve_cb):
    msgs = {"messages": [("system", SYSTEM), ("user", prompt)]}
    for attempt in range(3):
        try:
            result = agent.invoke(msgs, config)
            print(f"\n[ASSISTANT] {getattr(result['messages'][-1], 'content', '')}")
            return
        except GovernanceBlocked as e:
            label, reason = ("APPROVAL", str(e))
            if "approval" not in str(e).lower():
                print(f"[BLOCKED] {reason}"); return
            from .scenarios import EXPECTED_APPROVAL
            spec = EXPECTED_APPROVAL.get(version)
            ok = bool(approve_cb and spec and approve_cb(spec[0], spec[1], spec[2]))
            if not ok:
                print("  ↳ agent halts; a reviewer approves before this runs."); return
            msgs = {"messages": [("user", "continue")]}  # resume on same thread_id
```

- [ ] **Step 2: Verify against staging**

Run the v6 governed scenario end-to-end and confirm: the agent escalates, the grant lands, the agent resumes, the payment completes, and the dashboard shows the approval. (Manual; reuse `.env`.)
```bash
python -m apdemo.cli activate --version 6
python -m apdemo.cli run --version 6 --scenario governed
```
Expected: `[APPROVAL REQUIRED authenticated]` → (grant) → `[GOVERNED ✓ schedule_payment]` and a completed payment; the session trace shows `govern_escalate` → approved → `govern_allow`.

- [ ] **Step 3: Record + commit**
```bash
git add apdemo/agent.py apdemo/scenarios.py LIVE-FINDINGS.md && git commit -m "feat: real approve-and-resume on the LangGraph path (Path A/B per spike)"
```

---

## Task 9: CLI — version ranges 0–8 + `apdemo approve`

**Files:**
- Modify: `apdemo/cli.py`

- [ ] **Step 1: Widen the version ranges**

In `apdemo/cli.py`, change the `activate` choices from `range(1, 7)` to `range(1, 9)` and the `run` choices from `range(0, 7)` to `range(0, 9)`.

- [ ] **Step 2: Add the `approve` subcommand**

After the `status`/`teardown` parsers, add:
```python
    ap = sub.add_parser("approve",
        help="operator grant for a pending action (POST /v1/govern/approve)")
    ap.add_argument("--tool", required=True)
    ap.add_argument("--arg", action="append", default=[],
                    help="key=value (repeatable) — the exact tool args to approve")
```
And in the dispatch body:
```python
    if args.cmd == "approve":
        import httpx
        s = ensure_live(s)
        kv = dict(a.split("=", 1) for a in args.arg)
        r = httpx.post(f"{s.url}/v1/govern/approve",
                       headers={"Authorization": f"Bearer {s.require_pat()}"},
                       json={"agent_id": s.agent_id, "tool": args.tool, "args": kv},
                       timeout=15)
        print(f"approve {args.tool}({kv}) -> {r.status_code} {r.text[:160]}")
        return 0 if r.status_code < 400 else 1
```

- [ ] **Step 3: Smoke-check the parser**

Run: `python -m apdemo.cli run --version 8 --scenario happy -h >/dev/null && python -m apdemo.cli approve -h >/dev/null && echo ok`
Expected: `ok` (argparse accepts version 8 and the new subcommand).

- [ ] **Step 4: Commit**
```bash
git add apdemo/cli.py && git commit -m "feat: CLI version ranges 0-8 + apdemo approve (operator grant)"
```

---

## Task 10: Provision — cover 8 versions

`provision.py`'s `activate(n)` already creates+publishes+assigns on demand and `version_body(n)` already uses `rules_for_version(n)`, so no client change is needed beyond confirming it accepts the new versions. Approver = the PAT's own user, which `/v1/govern/approve` already authorizes — no provisioning change.

**Files:**
- Modify: `tests/test_provision_bodies.py`

- [ ] **Step 1: Extend the body test to v8**

Add to `tests/test_provision_bodies.py`:
```python
from apdemo.provision import version_body


def test_version_body_covers_new_ladder():
    for n in range(1, 9):
        body = version_body(n)
        assert "rules" in body and "change_note" in body
    # v8 carries the catalog-governance rules
    kinds = [r["kind"] for r in version_body(8)["rules"]]
    assert "Conditional" in kinds and "PerToolRateLimit" in kinds
```

- [ ] **Step 2: Run**

Run: `pytest tests/test_provision_bodies.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**
```bash
git add tests/test_provision_bodies.py && git commit -m "test: provision bodies cover the 8-version ladder"
```

---

## Task 11: Guide — walk v0→v8 with real approval pauses

**Files:**
- Modify: `apdemo/guide.py`

- [ ] **Step 1: Replace the `STEPS` list** with 9 entries (v0–v8) whose `title`/`why`/`scenario`/`watch` match the new ladder (cowsay observe → content block+redact → rate limit → PII → block payment → approval → context fraud → catalog). Use `change_note(v)` for the "TapPass change" line (already wired). The `_approve` callback (POST `/v1/govern/approve`) is unchanged and already implements the scripted grant.

Replace the `STEPS` list with:
```python
STEPS = [
    {"version": 0, "title": "v0 — the agent you sent us (ungoverned)",
     "why": "Your LangGraph agent with cowsay + calculator, talking straight to OpenAI.",
     "scenario": "happy", "watch": "Open the dashboard: nothing. No audit, no control."},
    {"version": 1, "title": "v1 — two lines, now observed",
     "why": "base_url → the TapPass gateway, and tappass.govern() around the tools.",
     "scenario": "happy", "watch": "Same answer — now a governed turn with a full trace."},
    {"version": 2, "title": "v2 — govern the cow's words",
     "why": "Policy blocks a banned name in the message and redacts emails out of it.",
     "scenario": "governed", "watch": "The cow won't say the banned name; an email is scrubbed."},
    {"version": 3, "title": "v3 — rate-limit the tool",
     "why": "cowsay is capped at 3 calls per 2 minutes, counted from the audit trail.",
     "scenario": "governed", "watch": "The 4th cowsay is blocked — rate_limited."},
    {"version": 4, "title": "v4 — stop data leaving",
     "why": "PII / secrets are blocked in the agent's output.",
     "scenario": "governed", "watch": "Reading out a bank number → blocked."},
    {"version": 5, "title": "v5 — gate the dangerous action",
     "why": "The payment write tool is blocked outright.",
     "scenario": "governed", "watch": "Scheduling a payment → blocked."},
    {"version": 6, "title": "v6 — human in the loop",
     "why": "Payments are allowed but each needs human approval.",
     "scenario": "governed", "watch": "The agent escalates; approve it and it resumes — "
                                       "the approval + execution are audited."},
    {"version": 7, "title": "v7 — context-aware (the fraud beat)",
     "why": "Small payments flow; large ones + bank-account changes need elevated approval.",
     "scenario": "governed", "watch": "A €25k payment escalates for sign-off."},
    {"version": 8, "title": "v8 — govern the agent that touches your catalog",
     "why": "The same kernel now governs an agent editing your Collibra-style catalog.",
     "scenario": "governed", "watch": "Weakening a data classification → blocked."},
]
```
Update the banner/closer text that says "v0→v6" / "Six policy versions" to "v0→v8" / "Eight policy versions".

- [ ] **Step 2: Manual walkthrough smoke (no assertion)**

Run: `python -m apdemo.cli guide --fresh` and press ENTER through; confirm each rung activates and the v2/v3/v6 beats fire. (Manual; needs `.env` + network.)

- [ ] **Step 3: Commit**
```bash
git add apdemo/guide.py && git commit -m "feat: guided walkthrough covers v0-v8 with cowsay + real approval beats"
```

---

## Task 12: README + LIVE-FINDINGS refresh

**Files:**
- Modify: `README.md`
- Modify: `LIVE-FINDINGS.md`

- [ ] **Step 1: Rewrite `README.md`**

- Reframe v0 as "the agent you sent us" and paste Collibra's `cowsay`/`calculator` + `tappass.govern` snippet as the starting point.
- Replace the v0→v6 ladder section with the v0→v8 ladder + talk track from the spec (cowsay observe → content block+redact → rate-limit → PII → block payment → approval → context fraud → catalog).
- **Delete** the "## Honest note on approvals (current state)" section — the round-trip is now real. Replace it with a short "## Approvals" section describing escalate → approve (dashboard or `apdemo approve`) → resume and where it shows in the audit + session trace (`govern_escalate` → approved-by → `govern_allow`).
- Update the command list to include `approve` and the 0–8 / 1–8 ranges.

- [ ] **Step 2: Refresh `LIVE-FINDINGS.md`**

Mark the stale "⏳ Remaining gap — live dashboard approve → resume" note as resolved (point to the Task 1 spike section + the shipped Path A/B), and update the version table to the new numbering.

- [ ] **Step 3: Commit**
```bash
git add README.md LIVE-FINDINGS.md && git commit -m "docs: reframe README around Collibra's snippet + v0-v8 ladder; approvals now real"
```

---

## Task 13: Full live verification

**Files:** none (verification only)

- [ ] **Step 1: Fresh provision + full ladder**

Run:
```bash
python -m apdemo.cli setup        # if not already provisioned; paste env if printed
python -m apdemo.cli guide --fresh
```

- [ ] **Step 2: Confirm each governance beat live** (check the dashboard trace per rung):
  - v1: cowsay/calculator audited (cost, latency, trace).
  - v2: banned name → `[BLOCKED]`; an email → redacted in the trace.
  - v3: 4th cowsay → `[BLOCKED] rate limit`.
  - v4: bank-number read-out → `pii_in_output` block.
  - v5: `schedule_payment` → `blocked_tool`.
  - v6: escalate → approve → resume; trace shows `govern_escalate` → approved → `govern_allow`.
  - v7: €25k payment + bank change → elevated approval.
  - v8: classification downgrade → blocked; schema change → approval.

- [ ] **Step 3: Run the unit suite green**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 4: Final commit (if any docs/fixups)**
```bash
git add -A && git commit -m "chore: live-verified v0-v8 ladder + approve-and-resume" || echo "nothing to commit"
```

---

## Notes for the implementer

- **TDD where deterministic** (tools, rules, scenarios, verdicts, agent wiring, provision bodies). The network-coupled behavior (approval resume, guide, live rungs) is verified manually against `app.tappass.ai` — same methodology as the existing `LIVE-FINDINGS.md`.
- **Arg-name contract:** policy rules read `request.tool_args.<name>`; the `@tool` signatures in `tools.py` define those names (`message`, `amount`, `classification`, …). Renaming a tool arg without updating `rules.py` silently breaks a rule.
- **Cumulative rules:** the cowsay content+rate rules persist from v2 onward (governance accretes). The 2-minute rate window resets quickly so it won't bite the later AP rungs.
- **API-version checks** are flagged inline (Task 6 Step 3a, Task 7 Step 3a). Mirror Collibra's working snippet for the `create_agent` / streaming surface when in doubt.
