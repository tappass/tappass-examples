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

## 🐛 OPEN — Conditional rules don't fire (server-side, owner to diagnose)

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

## Next build (approved): mediated execution for approvals

To make v4–v6 *approval* beats real (escalate → approve in dashboard → resume):
1. Call the gateway chat via httpx (not the OpenAI client) to capture the
   `capability_token` from the response when tool calls are present.
2. Per tool call: `POST /v1/tools/govern` `{capability_token, tool_call_id, name,
   arguments}` → allowed / blocked / escalate.
3. On escalate: poll `/v1/me/approvals/{request_id}/wait`; on approve, run the
   tool locally and continue. On block: feed a blocked tool-result back.

v5/v6 also depend on the Conditional fix above.
