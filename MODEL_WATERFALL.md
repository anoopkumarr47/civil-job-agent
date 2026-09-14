# Free-model provider waterfall

Research snapshot: 2026-09-14.

## Implemented production order

### 1. Cerebras — primary
- model: `gpt-oss-120b`
- secret: `CEREBRAS_API_KEY`
- optional variable: `CEREBRAS_MODEL=gpt-oss-120b`
- endpoint: `https://api.cerebras.ai/v1/chat/completions`

Cerebras receives every plausible vacancy. Routine roles use medium reasoning; senior/borderline/permit-sensitive roles use high reasoning.

### 2. Groq — independent reviewer and fallback
- model: `openai/gpt-oss-120b`
- secret: `GROQ_API_KEY`
- variable: `AI_MODEL=openai/gpt-oss-120b`

Groq reviews borderline/high-risk Cerebras decisions and becomes first fallback if Cerebras fails.

### 3. Gemini — optional tertiary/tie-breaker
- secret: `GEMINI_API_KEY`
- model variable: `GEMINI_MODEL=gemini-3.5-flash-lite`

Gemini is used only if the preferred providers fail or when an additional tie-break review is useful.

## Current Cerebras free-tier capacity

Cerebras currently documents approximately:
- `gpt-oss-120b`: 64K TPM
- 30 RPM
- 1M TPD

This is a separate quota pool from Groq.

## Analysis flow

```
broad deterministic capture
          ↓
Cerebras GPT-OSS 120B
 medium/high reasoning by risk
          ↓
 clear result ───────────────→ final policy gate
          │
 borderline/high-risk
          ↓
Groq GPT-OSS 120B independent review
          ↓
 disagreement / provider failure
          ↓
optional Gemini tie-break/fallback
          ↓
conservative consensus
          ↓
final permit/score gate
```

## Future providers

### Cloudflare Workers AI
Good independent quota pool and useful future fallback. Requires:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

### OpenRouter free router
Useful emergency low-volume fallback. Requires:
- `OPENROUTER_API_KEY`

The key design principle is that separate providers provide genuine quota/failure-domain diversification; multiple models within a single provider do not.
