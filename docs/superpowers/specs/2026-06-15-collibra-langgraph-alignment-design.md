# Collibra-Aligned LangGraph AP-Agent Governance Demo — Design

**Date:** 2026-06-15
**Status:** Approved (design), pending spec review → implementation plan
**Home:** `ap-governance-wt/openai-ap-governance/` (the `apdemo` package)
**Supersedes the agent-plumbing + approval parts of:** `2026-06-08-openai-ap-governance-demo-design.md`
**Audience:** Collibra (Nick) — and reusable for any prospect evaluating agent governance.

## Why this revision

Nick sent us a working "simple agent" he wants to run against the platform and treats as
the MVP yardstick. Two things follow:

1. **Make the demo recognisable to him.** His agent is **LangChain/LangGraph**
   (`langchain.agents.create_agent`, `langchain_openai.ChatOpenAI`,
   `langgraph.checkpoint.memory.MemorySaver`) wired to TapPass with the **SDK's own**
   `tappass.govern(tools, mode="enforce", agent_id=...)` plus a `base_url` swap to the
   gateway. Our current `apdemo` instead uses the **plain OpenAI SDK** with a
   **hand-rolled `httpx` `/v1/govern` loop** — functionally similar, but nothing on screen
   looks like his code. We align the agent's *plumbing* to his exact two-line shape, and
   seed the demo with his exact starter tools (`cowsay`, `calculator`).

2. **Make approvals real and legible.** The current demo *halts and surfaces* an approval
   but does not do the live escalate → human-approves → resume round-trip, and the audit/
   session trace shows the turn as a plain `allow`, not an approval (see the README's
   "Honest note on approvals" and `LIVE-FINDINGS.md`). We wire the **approve-and-resume
   (approval-as-fact)** flow that exists on `origin/main` so an approval **actually asks a
   human**, the agent **resumes** on approval, and the whole cycle is **clearly shown in
   the audit trail and session trace**.

The v0→vN *narrative* (ungoverned → observe → govern → approve → context-aware → govern the
catalog) is unchanged. Only the agent plumbing, the opening rungs (now on `cowsay`/
`calculator`), and the approval beat change.

## Design principles (carried forward + refined)

- **One reusable package, version-gated** — `--version N` still selects both the code
  surface (which tools the agent has) and the governance posture (which policy version is
  active). Strictly additive tool surface; governance grows in sophistication.
- **An ungoverned v0 baseline** — v0 is *his* agent verbatim: `ChatOpenAI` talks directly to
  OpenAI, tools **not** wrapped. No audit, no control.
- **One policy, versions activated one after another** — leverages TapPass's own
  draft→active→superseded lifecycle; the closer opens the version history as the audit of
  how governance evolved.
- **The "get governed" diff is his diff** — swap `base_url` to the gateway **and** wrap the
  tools with `tappass.govern(...)`. Those are the exact two lines in his snippet, and they
  map one-to-one onto the demo's two governance touch-points (gateway governs the LLM call;
  `/v1/govern` governs each tool call).
- **Govern his own tools first** — the first concrete governance beats act on `cowsay`/
  `calculator` (argument content, then call frequency) before any invoice appears. Playful,
  low-stakes, instantly recognisable; *then* escalate to money, fraud, and catalog.

## Architecture: the two governance touch-points = his two lines

```python
# v0 — ungoverned (his agent as-is): model → OpenAI directly, tools unwrapped.
model = ChatOpenAI(model=MODEL, base_url="https://api.openai.com/v1", api_key=OPENAI_KEY)
agent = create_agent(model, tools=raw_tools, checkpointer=MemorySaver())

# v1+ — governed: his exact two lines.
model = ChatOpenAI(model=MODEL, base_url=f"{TAPPASS_URL}/v1", api_key=AGENT_KEY)   # gateway governs the LLM call
tools = tappass.govern(raw_tools, url=TAPPASS_URL, api_key=AGENT_KEY,
                       mode="enforce", agent_id=AGENT_ID,
                       session_id=session_id, user_id=USER_ID)                     # /v1/govern governs each tool call
agent = create_agent(model, tools=tools, checkpointer=MemorySaver())
```

- The **gateway `base_url` swap** routes the LLM call through TapPass → audit, cost,
  latency, and output PII/secret scanning.
- **`tappass.govern(mode="enforce")`** wraps each tool so every call POSTs `/v1/govern`
  before running; a block raises `GovernanceBlocked` (the tool never runs); an approval
  drives the approve-and-resume flow below.
- The hand-rolled `govern_tool_call` / `report_tool_result` `httpx` code in `agent.py` is
  **deleted** — the SDK owns that path now. This is a net simplification *and* makes the
  governance call identical to what every customer integration uses.

### Verdict rendering (new design consideration)

Going full-LangGraph moves the governance decision *inside* the SDK wrapper + LangGraph's
tool node, so we lose the explicit per-tool decision prints the hand-rolled loop produced.
To keep the demo's signature verdict lines (`[GOVERNED ✓]` / `[BLOCKED <reason>]` /
`[APPROVAL REQUIRED <tier>]` / `[APPROVED ✓ resuming]`), add a thin **LangChain callback
handler** (`apdemo/verdicts.py`, a `BaseCallbackHandler`) that observes tool start / tool
error and renders the governance outcome:

- On tool start → print the tool + args being attempted.
- On `GovernanceBlocked` raised from the wrapper → print `[BLOCKED <reason>]` (the exception
  carries `reason` and `blocking_step`).
- On the approval path → print `[APPROVAL REQUIRED …]`, then `[APPROVED ✓ resuming]` after
  the human decides.
- On clean execution → print `[GOVERNED ✓ <tool>]`.

The handler is presentation-only; it never makes governance decisions. (Implementation
step 1 confirms the exact exception/return shape the SDK surfaces for the approval case —
see "Approvals" and "One thing to verify live".)

## The version ladder (9 rungs)

v0 = the ungoverned starting point. Each `vN (N≥1)` = one additive code increment and one
governance increment. Bold rungs are the new/changed ones.

| Ver | Tool surface (additive) | Governance posture (policy version) | The moment shown |
|---|---|---|---|
| **v0** | `cowsay(message)`, `calculator(a,b,op)`. `ChatOpenAI` → OpenAI directly, tools unwrapped. | **None** — not routed, no policy, no audit. | "This is the agent you sent us. Where did that call go? What did it cost? Who could stop it? You can't answer any of these." |
| **v1** | same | **Allow-all.** Gateway `base_url` + `tappass.govern(mode="enforce")`; no restrictive rules. | "Two lines changed — `base_url` and `tappass.govern`. We've blocked nothing, but now every LLM call and every tool call is in the audit trail with cost + latency." |
| **v2** | same | **Govern the cow's words (argument content).** `Conditional` block when `request.tool_args.message` matches a banned name/word; optional `RedactToolArg` to scrub a pattern from the message. | "Governance on your own tool's *arguments*. The cow may not say *that* — and we can redact a value out of it instead of blocking." |
| **v3** | same | **Frequency / velocity.** `PerToolRateLimit` on `cowsay`: at most **3 calls per 2 minutes**, counted from the **durable audit trail**. | "Run it again… and again — the **4th** is blocked `rate_limited`. The window is read off the audit log, so it holds across processes — not in-memory counting." |
| **v4** | + `lookup_vendor(vendor_id)`, `compute_invoice_total(line_items, tax_rate)` | **PII/secret block on output.** `BlockSecrets` + `BlockPII{output}`. | The IBAN read-out is blocked (`pii_in_output`) before it reaches the user. Same primitive as v2, higher stakes. |
| **v5** | + `schedule_payment(vendor_id, amount)` (a write) | **Tool-call enforcement.** `BlockTool` on the payment write. | Reads fine; the agent isn't cleared to move money, so the payment tool is blocked outright. |
| **v6** | same | **Human-in-the-loop approval — real escalate → approve → resume.** `RequireApproval` on `schedule_payment`. | The headline beat. The agent halts on a *real* pending approval; a human approves in the dashboard; the agent **resumes** and completes; the whole cycle is attributable to the rule in the audit + session trace. |
| **v7** | + `update_vendor_bank_details(vendor_id, iban)` (the AP-fraud vector) | **Context-aware.** `Conditional`: bank-detail changes *always* need elevated approval; payments over a threshold need elevated approval. | "Context, not a blunt threshold. The classic fraud vector — silently re-point a vendor's bank account — always needs sign-off." |
| **v8** | + `set_asset_classification(asset_id, classification)`, `propose_schema_change(asset_id, change)` | **Catalog governance, same kernel.** `Conditional`: downgrading a classification is **blocked**; schema change → elevated approval. | "The exact same governance kernel that gated payments now gates an agent editing your **Collibra catalog** — it can raise a classification but never weaken `Restricted`, and structural changes need sign-off." |

Governance capability arc: **(ungoverned) → observe → govern-my-own-tool-args →
rate-limit → redact/scan → tool-enforce → approve → context-aware → govern-the-catalog.**

### Rule kinds per rung (all natively expressible today — verified against the kernel)

All `input.*` paths and rule kinds confirmed in `kernel/policy/templates.py`,
`conditional.py`, `signal_catalog.py`, and `kernel/producers/tool_rate.py`. No custom
producer or rule-kind is required.

- **v2 — content block + redact:** `Conditional` with
  `when: {signal: "request.tool_args.message", op: "match"|"contains"|"eq", value: <banned>}`,
  `then: {action: "block", reason: "banned_message"}` — **plus** `RedactToolArg` with
  `{matchers:[{tool:"cowsay", arg:"message", pattern:<regex>}]}` (emits a `redact_tool_arg`
  obligation; the effect plane strips the span and allows the call). Two runs show both:
  blocked banned word, redacted sensitive token.
- **v3 — rate limit:** a single `PerToolRateLimit` with
  `{tool:"cowsay", max:3, window_seconds:120}`. Produced by `ToolRateProducer`, which queries
  `govern_allow` audit records in the window (`state.tool_rate.timestamps` / `.now_ns`).
- **v4 — output PII/secrets:** `BlockSecrets` + `BlockPII{scope:"output"}` (unchanged from
  the current `rules.py`). Note: PII/secret detection is **output/text-scoped**, not on raw
  tool args — so this beat necessarily sits on the LLM output, not on `cowsay`'s arg.
- **v5 — block write:** `BlockTool{tools:["schedule_payment"]}`.
- **v6 — approval:** `RequireApproval{tools:["schedule_payment"], tier:"authenticated", reason:…}`.
- **v7 — conditional fraud:** `Conditional` (bank-change always `require_approval` elevated)
  + `Conditional` (`schedule_payment` with `request.tool_args.amount > threshold` →
  `require_approval` elevated). (These are the current `rules.py` v5 rules, shifted.)
- **v8 — catalog:** `Conditional` (downgrade `set_asset_classification` to `public|internal`
  → `block`) + `Conditional` (`propose_schema_change` → `require_approval` elevated).
  (Current `rules.py` v6 rules, shifted.)

## Approvals: real approve-and-resume (approval-as-fact)

Chosen approach: **reuse `origin/main`'s approval-as-fact flow** (server commit `c401aba`),
rather than adding a new kernel "escalate-on-decision-path" code path.

**Mechanism (verified on `origin/main`):**

1. The agent calls a gated tool. The SDK posts `/v1/govern`. Policy has a
   `require_approval` rule; the `ApprovalProducer` finds **no grant** for this action's
   fingerprint (`fingerprint = agent_id + tool + args [+ model]`), so the call does **not**
   run — a pending approval is recorded.
2. **A human approves.** The headline path: a reviewer approves in the **TapPass dashboard**
   (`GET /v1/me/approvals` → `POST /v1/me/approvals/{request_id}/decide`). The scripted/CI
   path: an operator grant via `POST /v1/govern/approve {agent_id, tool, args, reason}`,
   which records an approved fact keyed by the same fingerprint.
3. **The agent resumes.** On re-submission of the *identical* call, the `ApprovalProducer`
   now returns `subject.approval.granted = true`, the `require_approval` obligation is
   suppressed, and the tool runs. The grant is **single-use** (atomically consumed), so a
   later identical call re-escalates.

**Audit + session trace (the second requirement) — what is shown:**

- The escalate turn is recorded as a distinct **`govern_escalate`** audit event carrying the
  approval evidence: `request_id`, `tier`, `matched_rule`, and (after decision) `decided_by`
  / `assertion_id`. This is attributable to the rule — not folded into an `allow`.
- The approval row transitions `pending → approved (by <user>)`, visible in the dashboard
  approvals list and linked to the turn by `request_id`.
- The resumed turn is recorded as **`govern_allow`** (the obligation was satisfied), tied to
  the same session/`pipeline_id` so the session trace reads as one legible sequence:
  **approval required (rule X) → approved by Y → executed.**
- The README's "Honest note on approvals" is **deleted** — the round-trip is now real.

**Demo harness integration (around the SDK):**

- Wrap the agent run so the v6–v8 approval beats are driven through the dashboard
  (headline) or `apdemo approve` (scripted). The verdict handler prints
  `[APPROVAL REQUIRED …]` then `[APPROVED ✓ resuming]`.
- `apdemo approve` is a thin CLI that calls `POST /v1/govern/approve` with the exact
  `{agent_id, tool, args}` of the pending action (so a single presenter can run the guided
  walkthrough hands-free). The "real" path remains: approve in the dashboard.
- `provision.py` ensures the PAT's user is a valid approver for the agent's org.

### One thing to verify live (implementation step 1)

The two kernel investigations disagreed on whether `origin/main`'s **first** `/v1/govern`
call for a `require_approval` action returns `outcome="escalate"` (with `approval.request_id`
— in which case the SDK's built-in `wait=True` long-poll on
`/v1/me/approvals/{id}/wait` auto-resumes) **or** a block-pending that the harness must
catch and resolve via grant + re-submit. **The chosen approve-and-resume design is robust to
both**: once the grant exists, the identical re-submitted call is allowed by the
`ApprovalProducer`. Step 1 of implementation runs a single live probe against staging
(`app.tappass.ai`, the same methodology as `LIVE-FINDINGS.md`) to confirm which resume path
is cleaner, and the harness uses that one (preferring the SDK's native `wait=True` if
escalate is confirmed).

## File-by-file change map (`apdemo/`)

- **`agent.py`** — rewrite around `langchain` + `langgraph` + `tappass.govern`. Delete
  `build_client_kwargs`, `govern_tool_call`, `report_tool_result`, the manual OpenAI tool
  loop. New `build_agent(version, settings, session_id)` returns a LangGraph agent
  (`create_agent(ChatOpenAI(...), tools=...)`); v0 path is unwrapped/direct-OpenAI. `run()`
  drives `agent` with the verdict callback handler and returns the `session_id`.
- **`tools.py`** — convert the registry to LangChain `@tool` functions. **Add `cowsay`**
  (his exact tool) at `min_ver=0` alongside `calculator`. Keep the AP + catalog tools,
  re-tagging `min_ver` to the new ladder (vendor/invoice=4, payment=5, bank=7, catalog=8).
  Keep a `tools_for_version(n)` that returns the raw `@tool` objects (the gating layer);
  `agent.py` wraps them with `tappass.govern`.
- **`rules.py`** — renumber to the 9-rung ladder and **add the two cowsay rungs**:
  v2 `Conditional` banned-message block (+ optional `RedactToolArg`), v3 `PerToolRateLimit`.
  v4–v8 are the current v2–v6 rule-sets shifted by two. Update `change_note`.
- **`scenarios.py`** — add v0–v3 prompts that exercise `cowsay`/`calculator` (a happy
  cowsay; a `governed` cowsay that says the banned word; a v3 prompt that calls cowsay
  repeatedly to trip the rate limit). Shift the AP/catalog prompts to their new versions.
  Extend `LONG_PROMPT` to open with a couple of cowsay calls.
- **`verdicts.py`** (new) — the LangChain `BaseCallbackHandler` that renders
  `[GOVERNED ✓]` / `[BLOCKED]` / `[APPROVAL REQUIRED]` / `[APPROVED ✓]`.
- **`cli.py`** — `--version` ranges become 0–8 (run) / 1–8 (activate). Add `apdemo approve`
  (operator grant for scripted runs). `setup`/`status`/`teardown`/`guide` unchanged in shape.
- **`guide.py`** — extend the guided walkthrough to v0→v8; the v6–v8 approval steps pause for
  a real approval (dashboard or `apdemo approve`) and then show the resumed completion + the
  trace link.
- **`provision.py`** — publish 8 policy versions (was 6); ensure the PAT user is an approver.
- **`pyproject.toml`** — add `langchain`, `langgraph`, `langchain-openai`; keep `openai`
  (transitive via `langchain-openai`), `httpx`, `python-dotenv`, `tappass` (the SDK).
- **`README.md`** — reframe v0 as "the agent you sent us" (his `cowsay`/`calculator`
  snippet), document the 9-rung ladder + talk track, replace the approvals-honesty note with
  the real escalate→approve→resume beat, and point explicitly at the `govern_escalate` audit
  event + the session-trace approval rendering.

## Testing

Mirror the existing `tests/` (pure, no network):

- `test_rules.py` — assert the 9-rung rule-sets, including the new v2 `Conditional`
  banned-message payload and v3 `PerToolRateLimit` payload (kind/ordinal/payload shape), and
  that the shifted AP/catalog rules are unchanged in content.
- `test_tools.py` — `cowsay` and `calculator` behave; `tools_for_version` gating matches the
  new `min_ver` map; tools are valid LangChain `@tool` objects.
- `test_scenarios.py` — every `(version, mode)` has a prompt; the v2 governed prompt contains
  the banned token; the v3 prompt drives repeated calls.
- `test_verdicts.py` (new) — the callback handler renders the four verdict strings from
  representative tool-start / `GovernanceBlocked` / approval events.
- `test_agent_helpers.py` — `build_agent` selects direct-OpenAI for v0 and gateway+govern for
  v1+, wires the session id, and applies the right tool set per version (mock the network).
- `test_provision_bodies.py` / `test_catalog.py` / `test_config.py` — adjust version counts.

Live verification (not in unit tests) reuses the `LIVE-FINDINGS.md` methodology against
`app.tappass.ai`: confirm the v2 block, v3 rate-limit, v6 approve-and-resume, and the
`govern_escalate` → `govern_allow` trace sequence.

## Out of scope (YAGNI)

- No new kernel "escalate-on-decision-path" code (we reuse main's approve-and-resume).
- No new policy rule-kinds or producers (all rungs use existing kinds).
- No WebAuthn/"signed" approval tier in the demo (use `authenticated`/`elevated`); the
  dashboard supports signed approvals but the demo doesn't need it.
- No input-scoped PII *detection* on tool args (v4 PII stays on LLM output, where detection
  runs); arg-level scrubbing is the `RedactToolArg` pattern in v2.

## Decisions (resolved at spec review)

1. **Rate-limit scope (v3):** `cowsay` **only**, `max=3`, `window_seconds=120` (3 calls per
   2 minutes) — the block visibly lands on the 4th press. Single `PerToolRateLimit` rule.
2. **v2 content beat:** **block + redact flourish.** v2 blocks `cowsay` when the message
   matches a banned word/name (`Conditional`), **and** shows `RedactToolArg` scrubbing a
   pattern (e.g. an email/secret-looking token) out of the message instead of blocking — two
   runs, one rung: "block what's forbidden, redact what's sensitive."
3. **Approver identity:** approve as the **PAT's own user** (simplest provisioning). The
   trace shows the agent acted and that user approved; segregation-of-duties (a distinct
   reviewer user) is a later enhancement, not in this build.
