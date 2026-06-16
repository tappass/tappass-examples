# Live verification findings — AP governance demo

Validated against `https://app.tappass.ai`, org **`collibra-ba9ed2`** (the PAT's
resource org; `/api/me` reports the *home* org `tappass-6ab653`, which differs).
Agent `ap-demo-agent` (`ag_59KoBIpA`). Policy `AP Demo Policy (2)`
(`111da0e4-e7df-4ce0-a391-63af9932cd76`).

## ✅ Working, verified live

| Ver | Control | Path | Result |
|---|---|---|---|
| v0 | none (direct OpenAI) | — | calculator runs, correct answer, no TapPass |
| v1 | allow-all | gateway `/v1/chat/completions` | runs, answer correct, audited |
| v2 | `BlockPII{output}` + `BlockSecrets` | gateway (LLM_CALL output scan) | IBAN read-out **blocked** (`pii_in_output`) |
| v3 | `BlockTool{schedule_payment, update_vendor_bank_details}` | `/v1/govern` (TOOL_CALL) | writes **blocked** (`blocked_tool:*`); `calculate` allowed |

Prereq resolved: org had **no BYOK key** → registered OpenAI key via
`POST /api/admin/llm-keys {provider:"openai", api_key}` (verified active). The
gateway uses per-org BYOK, **not** the agent's `OPENAI_API_KEY`. Without it the
gateway returns a `call_llm` block ("LLM call failed").

## Governance architecture (as observed)

- **Gateway `/v1/chat/completions`** governs the **LLM_CALL** (enforces output
  PII/secrets). When the model emits tool calls it mints a **capability token**
  and returns `tool_tracks`; it does **not** block individual tools inline.
- **Decision-only `/v1/govern`** governs a **TOOL_CALL** (`{type:"TOOL_CALL",
  agent_id, session_id, behavior_id, payload:{tool, args, server}}`, Bearer =
  agent key). Enforces **block** (BlockTool, and Conditional-block once the bug
  below is fixed). **Does NOT enforce approval** — `require_approval` comes back
  as an *obligation* with `outcome:"allow"` (see `kernel/enforce.py`: only the
  `enforce()` / mediated path runs `apply_obligations` → `ApprovalRequired`).
- **Mediated `/v1/tools/execute` (or `/tools/govern`)** + capability token is the
  path that enforces approval obligations → real escalate → approve → resume.

## Control-plane lifecycle facts (baked into provision.py)

- **Onboard must OMIT `org_id`** (server resolves resource org from the PAT;
  passing the home org → 403). Read `org_id` back from the onboard response.
- **One open draft per policy** (ADR 0014); **active version moves forward only**
  (`pull-back` reverts *active*→draft; a *retired* version cannot be
  re-activated). ⇒ `activate(n)` = create vN draft → publish → assign, atomically,
  using the server's returned `version_no`. No `version_map` needed.
- **Policies can't be deleted** via API (`405`) and **names are unique per org**
  ⇒ `create_policy` retries with a numeric suffix.
- **Reusing an agent**: onboard 409s → look it up in `/api/agents` and mint a
  fresh key via `POST /api/agents/{uuid}/developer-keys`.
- **Tool args** are exposed to Rego as **`request.tool_args.*`** (NOT
  `request.args.*`). `signal_catalog.py` confirms `request.tool_args.*`.

## ✅ FIXED & DEPLOYED — Conditional rules now fire

Root cause: `compose_agent` (kernel/policy/bundle.py) rebuilt the
`data.tappass.rules` sidecar from raw `r.payload`. For simple kinds the
rendered sidecar equals the payload, so it was invisible — but a Conditional's
compiled sidecar is `{v, reads}` (the literals the Rego reads as `.v[...]`), NOT
the raw `{when, then}`. So `data.tappass.rules[id].v` was absent → every leaf
compared against undefined → silent allow. Fix: a pure `sidecar_for_rules()`
helper builds the sidecar with the SAME `render()` that built the Rego.
Shipped in PR #651 → v0.8.27 (prod). Verified live: a re-activated v6
`set_asset_classification(classification="internal")` now returns
`block | rule_kind=Conditional`. Re-activate (recompose) after deploy is required
— the fix only affects newly-composed bundles.

NOTE: Conditional `require_approval` actions (v5 threshold/bank, v6 schema) now
MATCH correctly but still return `allow` on the decision-only `/v1/govern` path
(approval is an obligation; only mediated execution escalates — see below).

---
### Original diagnosis (kept for reference)

`BlockTool` works, but `Conditional` rules (v5 amount threshold, v6
classification block) evaluate to `allow` despite **correct-looking compiled
Rego**:

```rego
_cond_X_1 if { input.request.tool == data.tappass.rules["X"].v["1"] }            # set_asset_classification
_cond_X_2 if { input.request.tool_args.classification in data.tappass.rules["X"].v["2"] }  # ["public","internal"]
_cond_X_0 if { _cond_X_1; _cond_X_2 }
step contains s if { _cond_X_0; s := {"act":"block", "reason":"agent may not weaken a data classification"} }
```

Probe `set_asset_classification(classification="internal")` → `allow` (expected
block). Not caching (re-probed a long-active version), not the signal path.

**Hypothesis:** the Conditional rules appear in `merged_floor.rules[<id>]`
carrying their raw `{when, then}` spec, while the Rego reads
`data.tappass.rules[<id>].v["1"]/.v["2"]` (the compiled literal sidecar).
`BlockTool` works because its `.v["0"]` sidecar IS populated. It looks like the
Conditional `v`-sidecar is **not merged into `data.tappass.rules` at eval time**
(it's in `merged_floor` as `{when,then}` instead), so every `.v[...]` lookup is
undefined → leaf never matches. Owner territory: `kernel/policy/conditional.py` +
the bundle composer / data-doc assembly.

Get the full effective bundle to confirm:
`GET /api/agents/ag_59KoBIpA/policy/effective` → `merged_rego`, `merged_floor`.

## ✅ BUILT — tool governance via /v1/govern per tool call

The agent (`agent.py`) now governs EVERY tool call through `/v1/govern` before
running it (v1+), and honors the verdict: `block` → don't run; a
`require_approval` obligation → halt and surface the tier/reason; else run.
Verified live end-to-end through `apdemo run`:
- v3 `schedule_payment` → BLOCKED.
- v5 €25k payment → APPROVAL REQUIRED (elevated); €500 → allowed; bank-change →
  APPROVAL REQUIRED (elevated).
- v6 classification downgrade → BLOCKED; schema change → APPROVAL REQUIRED;
  raise-classification → allowed.

**Why NOT the capability-token "mediated execution" path** (tested live and
rejected): `/v1/tools/govern` (Track B) is decision-only — returns `allowed:true`
for a require_approval tool and drops the obligation entirely. `/v1/tools/execute`
(Track A) tries to RUN the tool server-side ("Unknown provider" for local tools).
So `/v1/govern` is strictly better here — post the Conditional fix it returns the
`require_approval` obligation cleanly, which the agent honors.

### ⏳ Remaining gap — live dashboard approve → resume
The decision path returns the obligation but creates NO approval request
(`approval: null`), and there is no decision-path endpoint to create one; approval
requests are only persisted by the ENFORCE path (chat LLM-call obligations, or
Track A server-executed tools). So the demo currently HALTS on approval and
surfaces it ("a reviewer approves in the dashboard") but does not yet do the live
round-trip. To close it: either (a) register the tools as server-side providers so
`/v1/tools/execute` enforces + persists the request, or (b) wire the approval-as-
fact re-submit flow (project_fingerprint_approval_kernel) — agent creates/awaits a
request, human decides, agent re-submits the govern call with
`input.subject.approval.granted=true` so the obligation no longer fires.

NOTE: don't put an IBAN/secret in an approval-scenario prompt — the v2 PII rule
blocks the CHAT (`pii_in_output`) before the tool call is reached.

---
### Original cap-token contract (kept for reference)

To make v4–v6 *approval* beats real (escalate → approve in dashboard → resume),
switch the agent's tool handling from local-only to the Track B (app-executes)
mediated flow:

1. **Capture the capability token.** Call the gateway chat via httpx (the raw
   OpenAI client hides it). The token is in the response JSON at
   `resp["tappass"]["capability_token"]` whenever the assistant message has
   tool calls. (`adapters/openai.py:139` sets `resp["tappass"]["capability_token"]`.)
2. **Govern each tool call (Track B).**
   `POST /v1/tools/govern` (Bearer = agent key) with
   `{capability_token, tool_call_id, name, arguments}`.
   - allowed → `{"allowed": true, ...}` (may return approved `arguments` for
     withheld args) → run the tool locally, feed the result back.
   - blocked → `{"allowed": false, "blocked_by": <step>, "reason": ...}` (HTTP
     200 for govern; execute returns 403) → feed a blocked tool-result back.
   - approval → **TO VERIFY LIVE**: confirm whether `mode="govern"` enforces the
     `require_approval` obligation (returns escalate / not-allowed-pending) or
     only `mode="execute"` does. `governed_tool(mode=...)` is in
     `surfaces/gateway/service.py`. If govern doesn't escalate, use
     `POST /v1/tools/execute` (Track A) — but that path expects TapPass to run
     the tool, which doesn't fit local Python tools; needs checking.
3. **Approval resume.** On escalate, poll `/v1/me/approvals/{request_id}/wait`
   (a human approves in the dashboard), then continue.

Request models (`adapters/openai.py`): `ToolGovernRequest` /
`ToolExecRequest` = `{capability_token, tool_call_id, name, arguments}`.

v5/v6 also depend on the Conditional fix above.

## 2026-06-15 alignment spike (Task 1) — against app.tappass.ai

Run with the new 9-rung `apdemo`. Three findings; two are blockers owned by the
**deployed server**, not the demo code.

### 1. Decision-only `/v1/govern` does NOT escalate (confirms original finding)
A `require_approval` (`RequireApproval` kind) tool call returns
`outcome="allow"` + a `require_approval` **obligation**, `approval: null`. No
escalate, no persisted approval request on this path.

### 2. SDK enforce wrapper therefore does NOT hold the tool
`tappass.govern(mode="enforce")` only raises `GovernanceBlocked` on
`outcome="block"`. Given finding #1 it returns the allow Decision and **runs the
tool** (verified: `gp("V-1001",4500)` → `TOOL_RAN`). ⇒ approvals must be
expressed as a **block-when-ungranted** Conditional (Path B), not `RequireApproval`.

### 3. Approval-as-fact resume is BROKEN on the deployed server
With a Conditional `block when (tool==schedule_payment AND
subject.approval.granted != true)`:
- before grant → `block "approval required"` ✓ (so `subject.approval.granted` IS
  supplied as `false` — the producer runs)
- `POST /v1/govern/approve {agent_id,tool,args}` → `200 {state:"approved",
  fingerprint:fp_43b9…}` — a real grant is recorded ✓
- **re-submit identical call → still `block "approval required"`** ✗
- second re-submit → still block.
⇒ The grant is recorded but **never consumed** on the `/v1/govern` path (fingerprint
mismatch between the two endpoints, or the consume-wiring isn't in the deployed
release). Net: the agent **cannot resume**. "Approval actually asks" ✓ (real block +
real recorded grant, visible in the approvals list/audit) but "resume" ✗.

### 4. v2 rule kinds: Conditional block WORKS, RedactToolArg BREAKS
- `Conditional {when: request.tool_args.message match "(?i)(voldemort|enron)",
  then: block}` → clean "hi" allow; "voldemort" → `block "the cow may not say that"`. ✓
- `BlockToolArgMatch` (same `{tool,arg,pattern}` matcher shape) → works. ✓
- **`RedactToolArg`** (same matcher shape, redact obligation) → **every** cowsay call
  returns `block / policy_eval_failed` (hard Rego eval error, fail-closed). ✗ Deployed-
  server bug specific to the `RedactToolArg` obligation rule.

### Consequences for the build
- v2 "block + redact flourish": the **block** half ships; the **redact** half
  (`RedactToolArg`) cannot until the server is fixed.
- Real **approve-and-resume** (requirement #2) is **not achievable** against the
  current deployed server via `/v1/govern` — needs a server-side fix (consume the
  grant on the decision path, or make the path escalate+persist).

### CORRECTIONS after root-causing (2026-06-15, same day)

**Finding #4 (RedactToolArg) was a PATTERN bug, not a rule-kind bug.** Reproduced
locally with regorus: the v2 redact pattern `[\w.+-]+@[\w-]+\.[\w.-]+` uses Unicode
`\w`, whose class expansion makes the compiled regex exceed regorus's 100 KB limit
→ the whole policy fails closed (`policy_eval_failed`) on EVERY call. The same `\w`
pattern breaks `BlockToolArgMatch` too — so it is NOT RedactToolArg-specific. An
ASCII-only pattern (`[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]+`) compiles small and
works: clean→allow, email→allow+`redact_tool_arg` obligation. Fixed demo-side in
`apdemo/rules.py` (97ae1f5). NO server change needed for this.
(Optional server hardening: validate/▸reject oversized user regexes at policy-author
time with a clear error instead of a runtime fail-closed `policy_eval_failed`.)

**Finding #3 (approval resume) IS a real server bug — fix PR opened.** Root cause:
`grant_action` stored the grant under the OPERATOR's org (`ctx.actor.org_id`) but the
ApprovalProducer claims it under the AGENT's org on re-govern; those differ for a
cross-org PAT (home org vs the agent's resource org). The fingerprint does NOT include
org_id, so only the store key was wrong. Fix = resolve the agent's org and store the
grant there → `tappass/tappass` PR #751
(`fix/approval-grant-agent-org-scoping`). Awaiting review + deploy. Once deployed, the
demo's v6–v8 approve→resume beats can be finished/verified.

NOTE (demo-tuning, deferred): live v2 email probe returns `block pii_in_output` ALONGSIDE
the `redact_tool_arg` obligation — so the "allowed but scrubbed" redact beat needs a
redact target that isn't independently flagged as PII (or a reframed narration). To
resolve when the paused demo work resumes.

### Final ladder verification (2026-06-15) — green against app.tappass.ai
With the final 9-rung rules (Path B approvals, ASCII redact):
- v1 cowsay/calculator audited; v2 'voldemort'→block "the cow may not say that",
  'ACME-4471'→allow+`redact_tool_arg`, vendor ids untouched.
- v3 cowsay 4th call → block `per_tool_rate_limit_exceeded:cowsay` (3/2min, from audit).
- v5 schedule_payment → block `blocked_tool:schedule_payment`.
- v7 pay €500 → allow; pay €25k → block "approval required … (elevated)"; bank change
  → block "approval required … (elevated)".
- v8 downgrade classification → block "agent may not weaken a data classification";
  raise → allow; schema change → block "approval required … (elevated)".
All approval beats HALT correctly (block + "approval required" reason); the SDK harness
grants the exact action + re-invokes. Full in-run RESUME (re-submit → allow) completes
once PR #751 (cross-org grant scoping) deploys — verified locally that GovernanceBlocked
propagates out of create_agent.invoke and the grant records.

### Demo rewired onto ADR 0016 needs_approval (2026-06-16, prod v0.9.6)
v6/v7/v8 approval rules switched from the block-when-ungranted hack to native
`require_approval` Conditionals (the compiler auto-gates them on
`subject.approval.granted`). Decision-only /v1/govern now returns a first-class
`needs_approval` + a persisted pending request (request_id); the SDK raises
`ApprovalPending` (not GovernanceBlocked); `_drive` catches it, approves the exact
governed action via /v1/govern/approve (which idempotently approves THAT pending
request — now dashboard-visible), and re-submits → allow. Verified live end-to-end
via the agent: v6 (€808), v7 (€15015 over-threshold), v8 (schema) all
halt→approve→resume→execute. The verdict×scope ledger (once/always/deny/revoke) +
migration 108 are deployed (v0.9.6). Known: the human-`/decide`-an-agent-request
path 404s (agent-created request has requester=nil, approver=self) — slice-1
follow-up; the operator-grant path works. Minor: v7 multi-attempt agent loop is
occasionally flaky (re-asks); clean runs + raw probe resume fine.
