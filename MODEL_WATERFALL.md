# AI resilience and model waterfall

Configuration snapshot: 2026-09-14.

The deterministic civil-domain and relocation gates run first. AI is reserved for plausible but non-obvious jobs.

## Production order

1. **Groq GPT-OSS 20B** — primary classification lane.
2. **Groq GPT-OSS 120B** — separate model fallback when 20B is rate-limited, temporarily unavailable, or returns invalid output.
3. **Gemini 3.1 Flash-Lite** — independent cross-provider emergency fallback.

One schema-valid adjudication is sufficient. Routine second opinions are disabled because they consumed Gemini's small free-tier request allowance without materially improving obvious classifications.

## Structured output

Both Groq GPT-OSS models use strict JSON Schema on every new job. If strict generation fails for one request, that request alone may retry JSON-object mode; future jobs return to strict mode.

Gemini uses `responseJsonSchema` and minimal thinking. It is not used unless both Groq model lanes are unavailable for the current vacancy.

## Rate-limit behavior

Groq rate-limit state is tracked per model. The response headers for remaining tokens and reset time are used to cool only the affected lane. A 20B TPM squeeze therefore switches immediately to 120B rather than provisionalizing the job.

Gemini 429 responses are distinguished between short RPM cooldowns and daily quota exhaustion. A daily quota failure disables Gemini for the rest of the run.

## Health semantics

A healthy production run requires:
- sufficient productive scraping sources;
- at least two operational configured AI lanes when multiple lanes are configured;
- provisional ratio no greater than 25% of AI-relevant assessments.

Temporary cooldown is not treated as permanent provider failure. The third emergency lane may be exhausted while two Groq lanes remain healthy without failing the sweep.

## Flow

```text
deterministic clear reject --------------------> reject
deterministic overwhelming clear civil -------> final policy
ambiguous / non-obvious
        |
        v
Groq GPT-OSS 20B
        |
        +-- failure/cooldown --> Groq GPT-OSS 120B
                                     |
                                     +-- failure/cooldown --> Gemini 3.1 Flash-Lite
                                                                    |
                                                                    +-- failure --> provisional
```

Provisional assessments are persisted but never notified as matches. They are retried on a later healthy run.
