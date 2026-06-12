# Incremental AP-Agent Governance Demo — Design

**Date:** 2026-06-08
**Status:** Approved (design), pending spec review → implementation plan
**Home:** `tappass-examples/openai-ap-governance/`
**Audience:** Collibra (and reusable for any prospect evaluating agent governance)

## Purpose

Show, step by step, how a "super basic OpenAI custom agent with a calculator tool"
grows into an agent under progressively more advanced TapPass governance — without
ever rewriting the agent. Each version `vN` adds **one** capability to the agent's
code surface and **one** governance posture, activated as a new version of a single
TapPass policy. The customer watches governance tighten, version by version, with the
full audit/version lifecycle on display in the dashboard.

The narrative is **Accounts Payable (AP)**: a concrete, high-stakes governance domain
(invoices, vendor bank details, payments, fraud). The closing version reframes the
exact same mechanism around "an agent editing your Collibra catalog."

## Design principles

- **One reusable package, version-gated** — not copy-pasted `vN/` folders. A single
  package where `--version N` selects both the code surface (which tools the agent
  has) and the governance posture (which policy version is active). The code surface
  is strictly additive across versions (tools only get added), so there is no drift;
  the governance posture grows in *sophistication* (v5 refines v4's blunt
  approve-all-payments into context-aware rules), which is itself a teaching point.
- **An ungoverned v0 baseline** — v0 is the agent the customer actually started with:
  the OpenAI client talks **directly** to OpenAI, not routed through TapPass at all.
  No audit, no cost visibility, no control. It exists to make the v1 contrast visceral
  ("one line changed — `base_url` — and now every call is observed").
- **One policy, six versions (v1–v6), activated one after another** — leverages
  TapPass's own policy version lifecycle (draft → active → superseded). `setup`
  creates all six versions up front as drafts; `activate --version N` flips the active
  version. v0 has no policy (it isn't routed). This *is* part of the demo story.
- **Mediated gateway** — the OpenAI client points at `https://app.tappass.ai/v1` via a
  `base_url` swap. LLM calls and tool calls flow through the gateway, giving full
  latency/cost/redaction telemetry in the dashboard. The agent code change to "get
  governed" is one line.
- **Reproducible via PAT** — a setup script drives the control-plane API with a
  Personal Access Token to create the agent + policy + versions idempotently and
  re-runnably. The PAT and the minted agent key live only in a gitignored local
  `.env` — never committed.

## The version ladder

v0 = the ungoverned starting point. Each `vN` (N≥1) = one agent code increment
(additive) + one governance increment.

| Ver | Agent gains (code surface) | Governance gains (policy version) | The moment shown |
|---|---|---|---|
| **v0** | Agentic loop + one tool: `calculate(expression)`. OpenAI client talks **directly** to OpenAI — no TapPass, no routing. | **None.** Not routed, no policy, no audit. | "This is the agent you have today. Where did that call go? What did it cost? Who can stop it? You can't answer any of these." |
| **v1** | Same `calculate(expression)`. One line changes: `base_url` now points at the TapPass gateway. | **Allow-all.** Agent registered, policy v1 = no restrictions. Pure observability. | "One line changed. Now every call is in the audit trail, with cost and latency — and we've blocked nothing." |
| **v2** | Adds `lookup_vendor(vendor_id)` → vendor record incl. IBAN/bank (PII); `compute_invoice_total(line_items, tax_rate)`. | **PII redaction + secret scan.** `BlockSecrets` + `BlockPII`/`RedactToolArg` so IBAN/bank numbers are redacted before reaching the model / logs. | A trace where the IBAN is redacted before it hits the model. |
| **v3** | Adds `schedule_payment(vendor_id, amount)` — a *write*. | **Tool-call enforcement.** `AllowTool` (read tools) + `BlockTool`/scoping so the payment *write* is gated; block a tool the agent isn't cleared for. | An allow vs block decision, per tool, visible in the trace. |
| **v4** | Same tools; demo prompt issues a real payment. | **Human-in-the-loop approval.** `RequireApproval` on `schedule_payment` → `escalate` → dashboard approval → agent resumes. | The escalate → approve → resume loop. Headline beat. |
| **v5** | Adds `update_vendor_bank_details(vendor_id, iban)` — the classic AP-fraud vector. | **Conditional / context-aware.** `Conditional` (nested AND/OR): bank-detail changes *always* require approval regardless of amount; payment over threshold → elevated approval. | Multi-signal, context-aware policy — not just thresholds. |
| **v6** (runnable closer) | Adds catalog tools: `set_asset_classification(asset_id, classification)` and `propose_schema_change(asset_id, change)` — the agent now acts on a **Collibra-style data catalog**. | **Catalog-change governance, same kernel.** `Conditional`: downgrading a `Restricted` classification is **blocked**; any schema change → **elevated approval**. | "The exact same policy mechanism that gated payments now gates changes to your data catalog itself — including the agent's attempt to *weaken* a classification." |

Governance capability arc: **(ungoverned) → observe → redact/scan → tool-enforce → approve → conditional-context → govern-the-catalog-itself.**

## Package architecture

```
tappass-examples/openai-ap-governance/
  apdemo/
    __init__.py
    config.py        # env loading: TAPPASS_URL, TAPPASS_PAT, agent key, model
    tools.py         # all AP tools; each tagged with the version that unlocks it
    agent.py         # agent loop (OpenAI via TapPass gateway), tools where min_ver <= VERSION
    provision.py     # PAT-driven control-plane calls (org/team/project/agent + policy/versions/assign)
    scenarios.py     # canned prompts per version (happy-path + the blocked/redacted/escalated one)
    cli.py           # apdemo setup | activate | run | status | teardown
  README.md          # the v0->v6 walkthrough + talk track
  .env.example       # documents required env; real .env is gitignored
  pyproject.toml     # deps: openai, httpx, python-dotenv
  .gitignore         # .env
```

Two dials that move together:
- `apdemo run --version N` runs the agent exposing only tools with `min_ver <= N`.
- `apdemo activate --version N` publishes/activates policy version N.

### Components (single responsibility each)

- **`config.py`** — resolves `TAPPASS_URL` (default `https://app.tappass.ai`),
  `TAPPASS_PAT` (control plane), the minted agent data-plane key, the model name, and
  `OPENAI_API_KEY` (used by v0's direct path, and by the gateway as BYOK if the org
  has no provider key configured). No secrets in source; everything from env /
  gitignored `.env`.
- **`tools.py`** — pure Python AP tool implementations against an in-memory fake
  vendor/invoice dataset (no real ERP). Each tool carries a `min_ver` tag and an
  OpenAI function schema. The fake dataset deliberately contains an IBAN so v2
  redaction is observable.
- **`agent.py`** — the OpenAI agentic loop: tool-call loop (model → tool_calls →
  execute → feed back → final), registering only tools unlocked at the chosen
  version. **v0 builds the client against OpenAI directly** (`OpenAI()` with the raw
  OpenAI key, default `base_url`) — the deliberately ungoverned baseline. **v1–v6
  build it against the gateway** (`OpenAI(base_url=f"{url}/v1", api_key=AGENT_KEY)`).
  Surfaces TapPass outcomes (block / redaction / approval-pending) from the gateway
  response and the SDK exception types where applicable.
- **`provision.py`** — thin client over the control-plane API (functions, not a CLI):
  `resolve_org()`, `ensure_team_project()`, `onboard_agent()`,
  `create_policy()`, `create_versions()` (all five drafts), `publish_version(n)`,
  `assign_to_agent(version)`, plus `teardown()`. Idempotent: re-running `setup`
  reuses existing entities by name rather than erroring.
- **`scenarios.py`** — per-version canned prompts: a "happy path" prompt that
  succeeds, and a "governed" prompt that triggers that version's control (nothing to
  trigger in v0/v1, a secret/PII in v2, the write in v3, an over-threshold payment in
  v4, a bank-detail change in v5, a classification downgrade in v6).
- **`cli.py`** — `argparse` CLI with verbs `setup`, `activate`, `run`, `status`,
  `teardown`. `run --version` accepts `0` (ungoverned, direct OpenAI) through `6`;
  `activate --version` accepts `1`–`6` (v0 has no policy to activate).

## Data flow

**Setup (once):**
```
PAT ──> GET  /api/me/access                       -> org slug + uuid
    ──> POST /api/teams, /api/projects            -> demo team/project
    ──> POST /api/agents/onboard                  -> agent_uuid + agent api_key (-> .env)
    ──> POST /api/v2/policies                     -> policy_id
    ──> POST /api/v2/policies/{id}/versions  x6   -> version_no 1..6 (drafts)
```

**v0 (ungoverned baseline):**
```
apdemo run --version 0 --scenario {happy|governed}
    agent ──> POST https://api.openai.com/v1/chat/completions  (raw OpenAI key)
              No TapPass involvement. No audit, no policy, no control.
```

**Per governed step (N = 1..6):**
```
apdemo activate --version N
    ──> POST /api/v2/policies/{id}/versions/{N}/publish     (activate version N)
    ──> POST /api/v2/policies/{id}/assignments {scope_type:agent, scope_id:agent_uuid}
apdemo run --version N --scenario {happy|governed}
    agent ──> POST https://app.tappass.ai/v1/chat/completions  (Bearer agent key)
              gateway resolves agent -> active policy version -> Rego -> verdict
              tool calls executed locally; writes/PII/approval gated by the verdict
```

## Rule mapping (grounded in core repo `tappass/kernel/policy/templates.py`)

- **v0** — no policy at all; the agent is not routed through TapPass.
- **v1 allow-all** — empty rule set (no `BlockTool`/`Block*`).
- **v2** — `BlockSecrets {}` + PII handling on the vendor record. Primary mechanism:
  `RedactToolArg`/`BlockPII {scope: "output"}` so the IBAN is redacted from
  model-bound content. (Exact redaction surface — tool-result vs prompt — pinned
  during implementation against the live trace.)
- **v3** — `AllowTool {tools: [calculate, lookup_vendor, compute_invoice_total]}` and
  `BlockTool`/scoping that gates `schedule_payment`.
- **v4** — `RequireApproval {tools: [schedule_payment], tier: "authenticated", reason}`.
- **v5** — two `Conditional` rules:
  - `when: request.tool == update_vendor_bank_details` → `then: require_approval (tier: elevated)`.
  - `when: request.tool == schedule_payment AND amount > threshold` → `then: require_approval (tier: elevated)`.
- **v6** — catalog-change rules (same kernel, new tools):
  - `when: request.tool == set_asset_classification AND new classification is weaker
    than current (e.g. Restricted → Internal)` → `then: block`. Expressed via
    `Conditional`; the current classification is supplied as a fact in `input` (the
    tool args carry asset_id + target classification, the catalog state carries the
    current one).
  - `when: request.tool == propose_schema_change` → `then: require_approval (tier: elevated)`.

## Error / outcome handling

The agent must render each governance outcome cleanly for the demo:
- **allow** → tool runs, normal output.
- **block** (`BlockTool`/`BlockSecrets`) → catch `PolicyBlockError`; print the
  blocking step + reason + audit URL. Agent does not execute the tool.
- **redaction** (`RedactToolArg`/`BlockPII`) → content is mutated; show the redacted
  value in the trace. (Optionally surface `RedactionApplied`.)
- **escalate** (`RequireApproval`/Conditional) → gateway returns approval-pending;
  the agent prints the approval URL and (for the demo) polls
  `/v1/me/approvals/{id}/wait`, then resumes once approved in the dashboard.
- **governance unavailable** → fail closed with a clear message (never silently allow).

## Testing strategy

- **Unit** — `tools.py` pure functions (invoice math, vendor lookup) tested directly;
  `provision.py` request-body builders tested without network (assert the exact JSON
  for each version's rules).
- **Live smoke** (manual, against `app.tappass.ai` with the PAT) — `run --version 0`
  (ungoverned, direct OpenAI) to confirm the baseline, then `setup`, then for each
  governed version 1–6: `activate --version N` + `run --version N --scenario governed`,
  asserting the expected outcome (allowed / redacted / blocked / escalated). This is
  the demo dress-rehearsal, run once before customer-facing use.
- No mock TapPass server; the value is in the real gateway/dashboard. Tests that need
  the network are clearly separated and skipped without a PAT.

## Security / handling of credentials

- PAT and minted agent key: env / gitignored `.env` only. `.env.example` documents
  names with placeholder values. Never written to any committed file, scenario, or
  README. Consistent with prior guidance (no credentials in shareable artifacts).
- The fake vendor dataset's IBAN is synthetic (documented as such) so redaction demos
  don't expose anything real.

## Open items to pin during implementation (have PAT + live env)

1. **LLM availability** — the gateway needs an upstream model for `/v1/chat/completions`.
   Confirm org `tappass-6ab653` has a usable provider key (BYOK) or a platform default,
   and the model name to use (e.g. `gpt-4o-mini`). Check via the llm_keys surface.
2. **Version pull-back** — confirm `publish` can activate an *older* version after a
   newer one is active (ADR 0014 "symmetric pull-back"). If not, fall back to:
   `setup` creates only v1; `activate --version N` creates+publishes version N (1..6)
   on demand.
3. **Exact redaction surface for v2** — whether IBAN redaction is best expressed as
   `RedactToolArg` (tool arg) or `BlockPII {scope: output}` (model-bound content);
   verify against a live trace.
4. **Approval resume** — confirm the gateway's escalate response shape on the
   `/v1/chat/completions` path and how the agent resumes after dashboard approval.
5. **v6 downgrade detection** — the "block a *weaker* classification" rule needs the
   asset's *current* classification visible to Rego as a fact in `input`. Confirm the
   cleanest way for this demo: have the agent pass both current + target in the tool
   args (Rego compares them via the classification ordering), versus a catalog
   producer that supplies the current state. Lean toward args-carry-both for demo
   simplicity, keeping the comparison ordering in the rule.

## Out of scope (YAGNI)

- Real ERP / banking integration (fake in-memory dataset only).
- Multi-agent / federation.
- A UI; the demo is CLI + the existing TapPass dashboard.
- Streaming (the basic completion path is enough; can add later if asked).
