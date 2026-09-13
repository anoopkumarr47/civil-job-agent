# Free-model provider waterfall feasibility

Research snapshot: 2026-09-13.

## Current production path

The current PR deliberately remains single-provider:

1. deterministic rules;
2. Groq `openai/gpt-oss-20b` for ambiguous vacancies;
3. Groq `openai/gpt-oss-120b` only for borderline/high-risk results;
4. provisional result if Groq remains unavailable after retries.

This keeps the first production baseline simple while materially reducing Groq token use.

## Recommended next provider: Cerebras

**Feasibility: high.**

Cerebras provides an OpenAI-compatible `/v1/chat/completions` API and a free API tier. Its current free-tier documentation lists `gpt-oss-120b` at approximately 64K TPM / 30 RPM / 1M TPD. This is a genuinely separate provider/account quota pool from Groq.

Integration work:
- add `CEREBRAS_API_KEY` GitHub secret;
- add a provider abstraction around endpoint/key/model;
- reuse the existing JSON validation contract;
- use Cerebras only after an exhausted Groq transient/quota failure, not for normal quality escalation;
- validate its structured-output behavior before enabling notifications.

Reference:
- https://inference-docs.cerebras.ai/support/rate-limits
- https://inference-docs.cerebras.ai/support/pricing

## Google Gemini Developer API

**Feasibility: medium-high.**

Google currently offers a free Gemini Developer API tier for certain models. Limits are project/model-specific and are shown in AI Studio rather than being guaranteed as a single static public table. This would provide a fully independent quota pool.

Integration work is higher than Cerebras because Gemini is not a drop-in OpenAI Chat Completions endpoint. We would add a small Gemini adapter and map its structured-output response into the same Assessment schema.

Privacy note: Google's free-tier documentation states free-tier content may be used to improve Google products. That should be considered before sending vacancy/candidate context.

References:
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits

## OpenRouter free models

**Feasibility: medium, fallback-of-last-resort.**

OpenRouter is OpenAI-compatible and offers `:free` models plus the `openrouter/free` router. However, without purchased credits the documented free-model allowance is only 50 requests/day total, and free-model availability/model selection can vary. That makes it useful as an emergency low-volume fallback, not a primary production classifier.

References:
- https://openrouter.ai/docs/faq
- https://openrouter.ai/docs/guides/routing/routers/free-router

## Mistral free mode

**Feasibility: medium-low for this agent.**

Mistral currently has a free/default API mode, but its documentation describes it as evaluation/prototyping with the lowest limits and directs users to their account Limits page for exact quotas. It could be added later, but Cerebras and Gemini offer clearer value for this workload.

Reference:
- https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them

## Recommended future cross-provider order

```
deterministic rules
      ↓
Groq GPT-OSS 20B
      ↓ quality uncertainty only
Groq GPT-OSS 120B
      ↓ provider/quota failure only
Cerebras GPT-OSS 120B
      ↓ provider failure / optional
Gemini free-tier Flash/Flash-Lite model
      ↓ emergency low-volume
OpenRouter free router
      ↓
provisional; retry next run
```

Important: switching between models inside one Groq organization is **not** treated as quota diversification. Cross-provider fallback only begins with Cerebras/Gemini/OpenRouter.
