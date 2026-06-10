# OpenAI AP-agent governance demo

A plain OpenAI "Accounts Payable" agent that starts **ungoverned** and, **one
policy version at a time**, grows into advanced TapPass governance — without ever
rewriting the agent. The whole point: governance is added *around* the agent, in
policy, activated live.

The narrative is Accounts Payable (invoices, vendor bank details, payments,
fraud); the closing version reframes the exact same mechanism around an agent
editing your **Collibra-style data catalog**.

---

## Quickest way to present: the guided walkthrough

```bash
apdemo guide
```

An interactive, press-ENTER-through tour of v0→v6. Each step shows the narration,
**what changes in TapPass** (+ the policy URL), waits for you to hit ENTER, applies
the governance change, runs the agent, prints the clear governance verdict
(`[GOVERNED ✓]` / `[BLOCKED]` / `[APPROVAL REQUIRED]`), and links the **governed
trace** in the dashboard. Keep `app.tappass.ai` open alongside and just press
ENTER.

**Re-runnable from a clean slate:**
```bash
apdemo guide --fresh
```
`--fresh` resets to a **brand-new policy** for the run — it neutralizes the
current policy (so it stops governing the agent) and mints a fresh one whose
version history starts cleanly at **v1**. Run it before every demo for a pristine
v1→v6 history. (Plain `apdemo guide` also re-runs correctly — it re-walks the
ladder on the existing policy — but the version numbers keep climbing across runs.)

The rest of this doc is the manual version of the same flow + the talk track.

---

## The showcase (manual, with full talk track)

Set up **two windows side by side**:
1. A terminal in this folder running `apdemo`.
2. A browser on the TapPass dashboard (`app.tappass.ai`) → the **`ap-demo-agent`**
   agent, and its **policy** (so you can show the version history + each governed
   turn's trace).

Then walk the ladder. For each version: **activate** the policy version (audience
sees a new version appear in the dashboard), **run** the agent, and point at the
trace. Two dials move together — `activate --version N` sets the governance
posture; `run --version N` exposes the tools unlocked at that step.

> Tip: run a fresh `apdemo setup` right before a demo so the policy's version
> history reads cleanly as v1…v6.

### v0 — the agent you have today (ungoverned)
```bash
apdemo run --version 0 --scenario happy
```
Calculator answer, correct — but it went **straight to OpenAI**. Open the
dashboard: **nothing**. *"Where did that call go? What did it cost? Who could
have stopped it? You can't answer any of these. This is most agents in production
today."*

### v1 — one line, now observed
```bash
apdemo activate --version 1     # allow-all
apdemo run --version 1 --scenario happy
```
Same answer. Now refresh the dashboard: the call is in the **audit trail** with
cost, latency, and a full input→decision→output trace. *"One line changed — the
`base_url`. We've blocked nothing. But now everything is observable."*

### v2 — stop data leaving
```bash
apdemo activate --version 2     # PII block + secret scan on output
apdemo run --version 2 --scenario governed   # asks for the vendor's bank number
```
`[BLOCKED] pii_in_output`. *"The agent tried to read a vendor's bank account
number back to the user. TapPass blocked it before it left."* Show the trace —
the block is attributed to the rule.

### v3 — gate the dangerous actions
```bash
apdemo activate --version 3     # block the write tools
apdemo run --version 3 --scenario governed   # tries to schedule a payment
```
`[BLOCKED] blocked_tool:schedule_payment`. *"Reads are fine. But this agent isn't
cleared to move money — so the payment tool is blocked outright."*

### v4 — human in the loop
```bash
apdemo activate --version 4     # payments require approval
apdemo run --version 4 --scenario governed
```
`[APPROVAL REQUIRED] … agent halts`. *"Now payments are allowed — but every one
pauses for a human reviewer. The agent stops and surfaces exactly what it wanted
to do and why it needs sign-off."*

### v5 — context-aware (the fraud beat)
```bash
apdemo activate --version 5
apdemo run --version 5 --scenario happy       # €500  → allowed
apdemo run --version 5 --scenario governed    # €25k  → elevated approval
apdemo run --version 5 --prompt "Update the bank details for vendor V-1002 to account 1234."
```
Small payment flows; the €25k payment needs **elevated** approval; **changing a
vendor's bank account always** needs approval. *"This is the classic AP-fraud
vector — silently re-point a vendor's bank account, then pay it. The policy knows
the difference between a routine payment and a risky one. Not a blunt threshold —
context."*

### v6 — govern the agent that touches your catalog
```bash
apdemo activate --version 6
apdemo run --version 6 --scenario governed    # downgrade a classification → BLOCKED
apdemo run --version 6 --prompt "Propose a schema change to invoice_lines: drop the tax_id column."
apdemo run --version 6 --scenario happy       # raise a classification → allowed
```
`[BLOCKED] agent may not weaken a data classification`; schema change →
**elevated approval**; raising a classification → allowed. *"The exact same
governance kernel that gated payments now gates an agent editing your **Collibra
catalog** — it can raise a classification, but it can never weaken `Restricted`,
and structural changes need sign-off."*

### The closer
Open the **policy version history**: six versions, activated one after another,
each with its change note — a full audit of how governance evolved. *"You watched
governance go from nothing to fraud-aware, catalog-aware control — by adding
policy versions, never touching the agent. That's the point: govern the behavior,
not the code."*

---

## What to point at in the dashboard
- **Agent** `ap-demo-agent` — the governed identity, its activity.
- **Audit trail / session trace** — each governed turn as input → decision →
  obligations → output. This is the trust artifact: every block/approval is
  attributable to a rule.
- **Policy → version history** — v1…v6 activated in sequence; the live
  draft→active→superseded lifecycle.

---

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e .
cp .env.example .env       # fill in TAPPASS_PAT and OPENAI_API_KEY
apdemo setup               # creates the agent + a fresh policy; prints 3 env vars
# paste the printed TAPPASS_AGENT_KEY / _UUID / _POLICY_ID into .env
```

`apdemo` commands: `setup` · `activate --version N` (1–6) · `run --version N`
(0–6) `[--scenario happy|governed] [--prompt "…"]` · `status` · `teardown`.

Credentials (PAT, agent key) live only in `.env` (gitignored) — never committed.

---

## Honest note on approvals (current state)

On the approval steps (v4–v6) the agent **halts and surfaces** the required
approval ("a reviewer approves in the TapPass dashboard"). The live
*click-approve-in-the-dashboard → agent-resumes* round-trip is **not yet wired** —
the decision path flags the approval but doesn't persist an approval request. For
a live demo, present approvals as **"the agent correctly refuses to act
autonomously and escalates"** — which is the governance guarantee that matters.
See `LIVE-FINDINGS.md` for the two ways to close the round-trip.

Demo gotcha: don't type an IBAN/secret into an approval prompt — the v2 PII rule
blocks the *chat* before the tool call is reached.
