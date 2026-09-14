# AI resilience and adaptive routing

Configuration snapshot: 2026-09-14.

The deterministic civil-domain and relocation gates run first. AI is reserved for plausible but non-obvious jobs.

## Production lanes

### Active workhorses
1. **Groq GPT-OSS 20B** — fast primary classifier.
2. **Cloudflare Llama 3.3 70B Fast** — independent provider sharing normal classification load.

The router balances successful classifications between these two lanes while respecting readiness/cooldown state. Cloudflare is capped by `CLOUDFLARE_RUN_CALL_BUDGET` (18 in production) because Workers AI's free allocation is shared across the UTC day and this agent runs twice daily.

### Reserve lanes
3. **Groq GPT-OSS 120B** — model-level reserve if both workhorses cannot serve the current vacancy.
4. **Gemini 3.1 Flash-Lite** — independent emergency reserve.

One schema-valid adjudication is sufficient. Routine second opinions are disabled.

## Cloudflare specifics

Workers AI uses the OpenAI-compatible chat-completions endpoint:

`https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions`

The production model is `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, which supports JSON Mode / JSON Schema output.

Cloudflare error handling:
- HTTP 429 internal code 3036 / free-allocation exhaustion: disable Cloudflare for the rest of that run.
- HTTP 429 internal code 3040 / out of capacity: temporary cooldown, then continue.
- auth/permission/model failures: disable only Cloudflare.
- schema incompatibility: retry JSON-object mode for that request only.

## Groq specifics

Both GPT-OSS models start each job in strict JSON Schema mode. A request may fall back once to JSON-object mode, but future jobs return to strict mode.

Rate-limit state is model-specific. If GPT-OSS 20B is temporarily constrained, the router can immediately use Cloudflare or GPT-OSS 120B.

## Gemini specifics

Gemini uses `responseJsonSchema` with minimal thinking. It is reserved for emergency cross-provider failover so its small free request allowance is not consumed by routine review traffic.

## Health semantics

`run_health.json` records:
- source health;
- lane vendor/model;
- requests and successful classifications;
- failures and last error;
- average latency;
- cooldown;
- Cloudflare per-run reserve remaining;
- provisional count and ratio;
- configured and operational independent vendors.

A production sweep is degraded when fewer than two independent configured AI vendors remain operational, or when more than 25% of AI-relevant assessments are provisional.

Temporary cooldown does not count as permanent vendor loss.

## Flow

```text
deterministic clear reject --------------------------> reject
deterministic overwhelming clear civil -------------> final policy
ambiguous / non-obvious
        |
        v
adaptive workhorse selection
   |                    |
Groq 20B          Cloudflare Llama 70B
   \                    /
    +------ failure/cooldown ------+
                                   v
                              Groq 120B
                                   |
                                   v
                         Gemini 3.1 Flash-Lite
                                   |
                                   v
                              provisional
```

Provisional assessments are persisted but never notified as matches. They are retried on a later healthy run.
