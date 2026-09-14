# AI resilience and provider waterfall

Configuration snapshot: 2026-09-14.

## Principle

The job agent must remain useful when AI is partially or completely unavailable. Deterministic civil-domain and relocation policy gates therefore run first. AI is reserved for ambiguity and non-obvious decisions.

## Decision tiers

### Deterministic reject
Clear non-civil/IT roles, early-career roles, foreign/Northern Ireland vacancies, explicit no-sponsorship blockers and other hard policy failures are rejected without consuming AI quota.

### Deterministic clear positive
An explicit high-confidence civil role can proceed without AI only when the deterministic score is at least the configured high-confidence threshold, the role family is not generic/risky, relocation is not low and no uncertainty/blocker gap remains.

Generic families such as Infrastructure Engineer, Project Engineer, Site Engineer, Project Manager and Design Engineer remain AI-gated even when their deterministic score is high.

### AI adjudication
All other plausible candidates above the review floor are sent to the provider waterfall.

## Provider order

### 1. Groq — primary

- model: `openai/gpt-oss-20b`
- secret: `GROQ_API_KEY`
- output: strict JSON Schema first, validated JSON Object fallback
- reasoning effort: low for normal classification; medium only when Groq is used as an independent second reviewer
- reasoning output: excluded

The workflow pins this model ID. It does not inherit legacy `AI_MODEL` or repository model variables.

### 2. Gemini — independent fallback/reviewer

- model: `gemini-3.5-flash`
- secret: `GEMINI_API_KEY`
- output: schema-constrained JSON first, validated JSON fallback

Gemini uses a separate provider and quota domain. If Groq is rate-limited, unavailable or request-incompatible, the current vacancy immediately switches to Gemini instead of waiting through repeated retries.

## Capability preflight

Before classifying real vacancies, each configured provider receives a tiny synthetic civil-vacancy request through the same production request path.

Preflight detects:
- invalid/expired credentials;
- billing/permission failures;
- missing/retired model IDs;
- structured-output incompatibility;
- malformed provider request configuration.

A provider that cannot pass either its structured mode or validated JSON fallback is disabled for that run. The other provider remains available.

## Circuit-breaker policy

- 401/402/403/404: disable only the affected provider for the run.
- 429: put that provider into a Retry-After-aware cooldown and fail over immediately.
- timeout/408/425/5xx: temporary cooldown and immediate failover.
- generic 400: do not disable the whole provider on the first real vacancy; request-format fallback is attempted first. Repeated independent 400s can disable it.
- provider response bodies are retained in health/log diagnostics.

## Run health

`run_health.json` records:
- productive source count;
- per-source job/error data;
- provider readiness/mode/cooldown/error state;
- AI calls by model;
- AI-relevant assessment count;
- provisional count and ratio.

A sweep is degraded when:
- no configured AI provider is ready;
- one of multiple configured providers is unavailable, reducing redundancy; or
- the provisional ratio exceeds the configured threshold (25% in production).

The workflow persists state and sends valid notifications before its final health gate. A degraded run then becomes visibly failed in GitHub Actions without discarding useful completed work.

## Flow

```text
scraping + dedupe
       |
       v
civil-domain / relocation gates
       |
       +---- hard reject --------------------> reject
       |
       +---- overwhelming clear civil fit ---> deterministic final
       |
       v
ambiguous / non-obvious candidate
       |
       v
provider capability state
       |
       +---- Groq GPT-OSS 20B
       |          |
       |          +-- success -------------> optional Gemini review
       |          |
       |          +-- failure/cooldown ----+
       |                                   |
       +-----------------------------------v
                                  Gemini 3.5 Flash
                                           |
                                           +-- success -> final policy
                                           |
                                           +-- failure -> provisional
```

Provisional assessments are persisted but never notified as matches. They are retried when a provider is healthy on a later run.
