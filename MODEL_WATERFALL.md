# Free-model provider waterfall

Research snapshot: 2026-09-14.

## Implemented now

The agent supports two independent providers:

### Groq
- primary: `openai/gpt-oss-20b`
- escalation/second opinion: `openai/gpt-oss-120b`
- existing secret: `GROQ_API_KEY`

### Google Gemini
- model: `gemini-3.5-flash-lite`
- secret: `GEMINI_API_KEY`
- optional variable: `GEMINI_MODEL`

Gemini 3.5 Flash-Lite is a stable high-throughput model with structured-output support. It provides a separate provider/quota pool from Groq.

When both providers are available, plausible jobs are split deterministically between them. Borderline/high-risk results request an independent opinion from the other provider and are consolidated.

## Why this is safer than reducing AI calls

The agent still skips deterministic hard rejects, but it does not skip strong plausible jobs simply to preserve tokens. Instead it:
- compresses vacancy evidence;
- distributes first-pass classification;
- gets a second opinion only where it can change the decision;
- retains plausible candidates when models disagree;
- caches unchanged jobs in state.

## Next provider: Cerebras

**Recommended next addition.**

Cerebras has an independent API/quota pool and an OpenAI-compatible `/v1/chat/completions` endpoint. Current free-tier documentation lists `gpt-oss-120b` at about:
- 64K TPM
- 30 RPM
- 1M TPD

It also supports strict JSON-schema responses.

Recommended use: third-provider fallback when Groq or Gemini is unavailable/quota-limited, and occasional tie-breaker for provider disagreement.

Required future secret:
- `CEREBRAS_API_KEY`

## Fourth provider: Cloudflare Workers AI

**Feasibility: good, but lower priority than Cerebras.**

Workers AI currently includes a 10,000-Neuron/day free allocation. Several free-plan models remain available, including `@cf/nvidia/nemotron-3-120b-a12b`, `@cf/google/gemma-4-26b-a4b-it`, and lighter models.

It is a separate quota pool but requires Cloudflare account configuration and uses Cloudflare-specific REST authentication.

Potential secrets:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

## Emergency provider: OpenRouter free router

OpenRouter offers free models and an OpenAI-compatible API. Accounts without purchased credits are currently limited to roughly 50 free-model requests/day total, so it is suitable as a low-volume emergency fallback rather than primary daily capacity.

Potential secret:
- `OPENROUTER_API_KEY`

## Recommended final provider order

```
Broad deterministic capture
        ↓
split first-pass load
   ┌───────────────┐
   │               │
Groq 20B      Gemini Flash-Lite
   │               │
   └──── second opinion on borderline/disagreement ────┘
                        ↓
                 consolidated assessment
                        ↓
        provider/quota failure or tie-break
                        ↓
               Cerebras GPT-OSS 120B
                        ↓
               Cloudflare Workers AI
                        ↓
               OpenRouter free router
                        ↓
                 provisional/retry
```

The key principle is that models inside one provider are quality tiers, not true quota diversification. Independent providers create the actual quota waterfall.
