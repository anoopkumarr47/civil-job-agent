# AI provider waterfall

Research/configuration snapshot: 2026-09-14.

## Production order

### Groq — primary
- model: `openai/gpt-oss-20b`
- secret: `GROQ_API_KEY`
- variable: `GROQ_MODEL=openai/gpt-oss-20b`
- endpoint: `https://api.groq.com/openai/v1/chat/completions`

The deterministic layer already extracts civil-domain, fit, salary, permit, experience and blocker evidence, so the 20B model is a more quota-efficient primary classifier than the prior 120B configuration.

### Gemini — independent fallback/reviewer
- model: `gemini-3.5-flash-lite`
- secret: `GEMINI_API_KEY`
- variable: `GEMINI_MODEL=gemini-3.5-flash-lite`

Gemini provides a separate provider/quota failure domain. It is used when Groq fails and for ambiguous/high-risk second opinions.

## Quota and failure controls

- compact decision evidence is capped by `AI_MAX_EVIDENCE_CHARS` (production default 4,200);
- model output is capped at 500 tokens;
- Groq calls are paced by `GROQ_MIN_INTERVAL_SECONDS`;
- provider API calls do not perform generic multi-retry amplification;
- permanent 400/401/402/403/404 provider errors trip a run-level circuit breaker;
- ambiguous provider failures remain provisional and are retried on later runs;
- unchanged jobs reuse persisted assessments;
- manual dry-runs load state read-only;
- live AI discovery is not triggered on every code push.

## Decision flow

```text
civil-domain + deterministic scoring
              |
              v
       Groq GPT-OSS 20B
          /          \
    clear result   ambiguous/risky
        |                |
        |                v
        |        Gemini Flash-Lite
        |                |
        +--------> conservative consensus
                         |
                         v
                 final policy gate

Groq unavailable -> Gemini fallback -> final policy gate
```

## Provider history

Cerebras was removed after live requests returned HTTP 402 Payment Required. Keeping an unusable primary provider added latency and pushed the entire fallback workload onto Groq.

A third provider should only be added if it provides a genuinely independent quota/failure domain and can preserve strict structured-output semantics.
