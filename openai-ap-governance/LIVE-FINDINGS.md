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
