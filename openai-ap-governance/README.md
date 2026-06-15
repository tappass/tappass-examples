# OpenAI/LangGraph AP-agent governance demo

A LangGraph "Accounts Payable" agent that starts **ungoverned** and, **one policy
version at a time**, grows into advanced TapPass governance — without ever rewriting
the agent. The whole point: governance is added *around* the agent, in policy,
activated live.

The agent is **Collibra's exact shape**: LangGraph + `ChatOpenAI` + two tools,
talking straight to OpenAI. Getting governed is two lines of the customer's own code.
The narrative is Accounts Payable (invoices, vendor bank details, payments, fraud);
the closing version governs an agent editing a **Collibra-style data catalog** with
the exact same kernel.

---

## Quickest way to present: the guided walkthrough

```bash
apdemo guide
```

An interactive, press-ENTER-through tour of v0→v8. Each step shows the narration,
**what changes in TapPass** (+ the policy URL), waits for you to hit ENTER, applies
the governance change, runs the agent, and prints the verdict
(`[GOVERNED ✓]` / `[BLOCKED]` / `[APPROVAL REQUIRED]`), and links the governed trace.
Keep `app.tappass.ai` open alongside and just press ENTER.

**Re-runnable from a clean slate:**
```bash
apdemo guide --fresh
```
`--fresh` resets to a **brand-new policy** — neutralises the current one and mints a
fresh policy whose version history starts cleanly at **v1**. Run it before every demo
for a pristine v1→v8 history. (Plain `apdemo guide` also re-runs correctly, but
version numbers keep climbing across runs.)

The rest of this doc is the manual version of the same flow with the full talk track.

---

## The two lines that govern the agent

The agent is an unmodified LangGraph app:

```python
# before (talking straight to OpenAI — v0)
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

model = ChatOpenAI(model="gpt-4o", base_url="https://api.openai.com/v1",
                   api_key=openai_api_key)
agent = create_agent(model, tools=tools, checkpointer=MemorySaver())
```

```python
# after — v1+ (two lines changed; agent code stays the same)
model = ChatOpenAI(model="gpt-4o", base_url="https://app.tappass.ai/v1",
                   api_key=agent_key)                         # ← line 1
tools = tappass.govern(tools, mode="enforce",                 # ← line 2
                       agent_id=agent_id, session_id=sid)
agent = create_agent(model, tools=tools, checkpointer=MemorySaver())
```

Line 1 routes the LLM call through the TapPass gateway (audit, cost, latency, output
PII/secret scan). Line 2 governs every tool call via `/v1/govern` before it runs —
a block raises `GovernanceBlocked`; an approval drives the halt-approve-resume flow.
The agent code never changes across v0–v8; **only policy does**.

---

## The showcase (manual, with full talk track)

Set up **two windows side by side**:
1. A terminal in this folder running `apdemo`.
2. A browser on the TapPass dashboard (`app.tappass.ai`) → the `ap-demo-agent` and
   its **policy** (version history + governed session traces).

For each version: **activate** the policy posture (the audience sees a new version
appear), **run** the agent, and point at the trace.

> Tip: run `apdemo setup` right before a demo so the policy version history reads
> cleanly as v1…v8.

---

### v0 — the agent you sent us (ungoverned)
```bash
apdemo run --version 0 --scenario happy
```
Calculator answer, correct — but it went **straight to OpenAI**. Open the dashboard:
**nothing**. *"Where did that call go? What did it cost? Who could have stopped it?
You can't answer any of these. This is most agents in production today."*

---

### v1 — two lines, now observed
```bash
apdemo activate --version 1     # allow-all (observability only)
apdemo run --version 1 --scenario happy
```
Same answer. Now refresh the dashboard: the call is in the **audit trail** with cost,
latency, and a full input→decision→output trace.

*"Two lines changed — `base_url` and `tappass.govern`. We've blocked nothing. But now
everything is observable."*

---

### v2 — govern the cow's words
```bash
apdemo activate --version 2
apdemo run --version 2 --scenario governed   # "say a cheerful hello, signed by voldemort"
```
`[BLOCKED] the cow may not say that`. Then run the redact beat:
```bash
apdemo run --version 2 --prompt "Make the cow say: order shipped — internal ref ACME-4471."
```
`[GOVERNED ✓]` — but the internal reference code **ACME-4471 is scrubbed** out of the
message before delivery (the `redact_tool_arg` obligation). Two beats in one policy
version: a banned name is blocked outright; a sensitive internal code is allowed but
cleaned.

*"The policy isn't a blunt door — it can distinguish 'stop this' from 'allow it, but
scrub the sensitive part'."*

---

### v3 — rate-limit the tool
```bash
apdemo activate --version 3     # cowsay capped at 3 calls / 2 min
apdemo run --version 3 --scenario governed   # asks for 4 separate cowsay calls
```
The first three go through; the fourth is `[BLOCKED] rate_limited`. The counter comes
from the **durable audit trail** — it survives process restarts.

*"The limit isn't in the agent code; it's in policy, counted from the immutable audit
record."*

---

### v4 — PII/secret block on output
```bash
apdemo activate --version 4
apdemo run --version 4 --scenario governed   # asks for the vendor's bank account number
```
`[BLOCKED] pii_in_output`. The agent retrieved the bank number and tried to surface it.
TapPass blocked it before it left.

*"The agent tried to read a vendor's bank account number back to the user. TapPass
intercepted it on the LLM output scan — after the model ran, before the response was
returned."*

---

### v5 — block the payment write tool
```bash
apdemo activate --version 5
apdemo run --version 5 --scenario governed   # tries to schedule a payment
```
`[BLOCKED] blocked_tool:schedule_payment`. Reads are fine; the write tool is blocked
outright.

*"Reads are fine. But this agent isn't cleared to move money — the payment tool is
blocked, full stop."*

---

### v6 — human in the loop (approve and resume)
```bash
apdemo activate --version 6     # payments require approval
apdemo run --version 6 --scenario governed
```
`[APPROVAL REQUIRED]` — the agent **halts**. In the guide, pressing ENTER calls
`POST /v1/govern/approve`, recording a real approval grant for the exact action.
The identical tool call re-governs to **allow** and the agent resumes. The block, the
recorded grant, and the allow are all visible in the audit/session trace.

*"The agent refuses to act autonomously and escalates. A reviewer approves the exact
action — not a category, not a permission flag. The agent then resumes, and every step
is in the audit trail."*

See the [Approvals section](#approvals-approve-and-resume) below for the mechanism and
the one current caveat.

---

### v7 — context-aware (the fraud beat)
```bash
apdemo activate --version 7
apdemo run --version 7 --scenario happy      # €500 → allowed
apdemo run --version 7 --scenario governed   # €25k → elevated approval
apdemo run --version 7 --prompt "Update the bank details for vendor V-1002 to account 7788."
```
Small payment flows; the €25k payment needs **elevated approval**; any change to a
vendor's bank account **always** requires approval, regardless of amount.

*"This is the classic AP-fraud vector — silently re-point a vendor's bank account, then
pay it. The policy knows the difference between a routine payment and a risky one. Not
a blunt threshold — context."*

---

### v8 — govern the agent that touches your catalog
```bash
apdemo activate --version 8
apdemo run --version 8 --scenario governed   # weaken a classification → BLOCKED
apdemo run --version 8 --prompt "Propose a schema change to invoice_lines: drop the tax_id column."
apdemo run --version 8 --scenario happy      # raise a classification → allowed
```
`[BLOCKED] agent may not weaken a data classification`; schema change →
`[APPROVAL REQUIRED]`; raising a classification → `[GOVERNED ✓]` allowed.

*"The exact same governance kernel that gated payments now gates an agent editing your
Collibra catalog — it can raise a classification, but it can never silently weaken
`Restricted`, and structural schema changes need sign-off."*

---

### The closer

Open the **policy version history**: eight versions, activated one after another, each
with its change note — a full audit of how governance evolved.

*"You watched governance go from nothing to fraud-aware, catalog-aware control — by
adding policy versions, never touching the agent. That's the point: govern the
behavior, not the code."*

---

## The governance ladder at a glance

| Ver | Control | The beat |
|-----|---------|----------|
| v0 | none — direct OpenAI | "Where did that call go? You can't say." |
| v1 | allow-all: gateway + `tappass.govern` | every call audited (cost, latency); nothing blocked |
| v2 | govern the cow's words | banned name → block; internal ref code → allow + scrubbed |
| v3 | rate-limit: cowsay ≤ 3 / 2 min | 4th call blocked `rate_limited`, counted from audit trail |
| v4 | PII/secret block on output | vendor bank number → blocked `pii_in_output` |
| v5 | block payment write tool | `schedule_payment` blocked outright |
| v6 | human-in-the-loop approval | agent HALTS; reviewer approves; agent RESUMES; all audited |
| v7 | context-aware (fraud beat) | small payments flow; >€10k and bank-detail changes → elevated approval |
| v8 | govern the catalog | weaken classification → blocked; schema change → approval |

---

## Approvals: approve-and-resume

**Why approval is a block, not a `RequireApproval` rule.** The SDK's enforce path only
halts a tool on `outcome="block"`. A `require_approval` obligation returns
`outcome="allow"`, so the tool would run ungoverned (verified live). Approval is
therefore expressed as a **block-when-ungranted** Conditional: the rule fires when the
target action is called AND `subject.approval.granted != true`. The SDK raises
`GovernanceBlocked`, the agent halts.

**The flow:**
1. The agent's tool call is blocked (`outcome="block"`, reason includes "approval required").
2. A reviewer approves — in the guide, pressing ENTER calls `POST /v1/govern/approve`;
   you can also approve in the dashboard. A real grant is recorded for the **exact** action.
3. The agent re-submits the identical tool call. The kernel's ApprovalProducer finds the
   grant and supplies `subject.approval.granted=true` → the block no longer fires →
   `outcome="allow"` → the agent resumes.
4. The audit/session trace shows: the block, the recorded grant, then the allow.

**The guarantee that always holds:** the agent refuses to act autonomously and
escalates. The approval is real and recorded, visible in the dashboard's approvals list
and audit trail.

**One caveat (PR #751):** The full in-run auto-resume requires a server-side fix. Root
cause: `grant_action` stored the grant under the operator's org, but the
ApprovalProducer looks it up under the agent's resource org — these differ for a
cross-org PAT. The fingerprint is correct; only the store key was wrong. Fix is in
`tappass/tappass` PR #751 (`fix/approval-grant-agent-org-scoping`), awaiting review
and deploy. Until it deploys: the agent correctly HALTS, a real grant is recorded, and
the demo shows the block and the grant in the dashboard — but the same-run auto-resume
completes only once #751 is live.

For a live demo before #751: present the approval beats as *"the agent refuses to act
autonomously and escalates — the approval is real and recorded."*

---

## What to point at in the dashboard

- **Agent** `ap-demo-agent` — the governed identity, live activity.
- **Audit trail / session trace** — each governed turn as input → decision →
  obligations → output. This is the trust artifact: every block and approval grant is
  attributable to a rule.
- **Policy → version history** — v1…v8 activated in sequence; the live
  draft → active → superseded lifecycle.

---

## Setup

**Dependencies:** `langchain`, `langgraph`, `langchain-openai`, `httpx`,
`python-dotenv`, and the `tappass` SDK.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
```

> **macOS-26 gotcha:** if `cryptography` fails to build from sdist, install its wheel
> first:
> ```bash
> pip install --only-binary :all: cryptography
> pip install -e .
> ```

```bash
cp .env.example .env
# Fill in: TAPPASS_PAT, TAPPASS_ORG (org slug), OPENAI_API_KEY
apdemo setup
# Paste the printed vars into .env:
#   TAPPASS_AGENT_KEY, TAPPASS_AGENT_UUID, TAPPASS_POLICY_ID
```

> **BYOK key required:** the TapPass gateway uses your org's registered LLM key (not
> the agent's `OPENAI_API_KEY`). Register it once in the dashboard under
> **Settings → LLM keys** (or `POST /api/admin/llm-keys`). Without it the gateway
> returns a `call_llm` block on every request.

**Credentials live only in `.env` (gitignored) — never committed:**

| Variable | What it is |
|----------|-----------|
| `TAPPASS_PAT` | Personal Access Token (control-plane auth) |
| `TAPPASS_ORG` | Org slug (e.g. `collibra-ba9ed2`) |
| `OPENAI_API_KEY` | Used by v0 only (direct OpenAI baseline) |
| `TAPPASS_AGENT_KEY` | Agent key (data-plane auth; printed by `setup`) |
| `TAPPASS_AGENT_UUID` | Agent UUID (printed by `setup`) |
| `TAPPASS_POLICY_ID` | Policy UUID (printed by `setup`) |

---

## Commands

```
apdemo setup                              # create agent + fresh policy; print env vars
apdemo activate --version N              # activate policy posture N (1–8)
apdemo run --version N                   # run the agent at version N (0–8)
         [--scenario happy|governed|long]
         [--prompt "…"]
apdemo guide [--fresh]                   # interactive guided demo (v0→v8)
apdemo approve --tool T [--arg k=v …]   # operator grant for a pending action
apdemo status                            # show active policy + assignment
apdemo teardown                          # remove demo agent + policy
```

The `long` scenario runs a full month-end AP sweep: cowsay, VAT calculation, a small
payment, a large payment, a bank-detail change, two catalog classification changes, and
a schema change proposal — all in one agent run. Useful for showing the full governance
surface in a single pass.
