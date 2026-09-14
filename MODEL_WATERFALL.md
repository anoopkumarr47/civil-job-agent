# Free-model provider waterfall

Research snapshot: 2026-09-14.

## Implemented production order

### 1. Groq — primary
- model: `openai/gpt-oss-20b`
- secret: `GROQ_API_KEY`
- variable: `AI_MODEL=openai/gpt-oss-20b`
- endpoint: `https://api.groq.com/openai/v1/chat/completions`

GPT-OSS 20B is used instead of 120B for routine job classification because the deterministic scoring layer already narrows the task and the smaller model reduces free-tier token pressure. It supports reasoning plus strict JSON-schema output.

### 2. Gemini — independent fallback/reviewer
- model: `gemini-3.5-flash-lite`
- secret: `GEMINI_API_KEY`
- variable: `GEMINI_MODEL=gemini-3.5-flash-lite`
- endpoint: Google Generative Language API

Gemini Flash-Lite is used when Groq fails and as an independent reviewer for ambiguous/high-risk decisions. Keeping it on a separate provider gives a genuinely separate quota and failure domain.

## Why Cerebras was removed

The 2026-09-14 live GitHub Actions run returned HTTP 402 Payment Required from Cerebras for every attempted classification. Because that status is not transient, repeatedly attempting Cerebras added latency without adding reliability.

## Quota-safety changes

- Groq output cap reduced to 500 tokens.
- Evidence packet default reduced from 6,000 to 3,600 characters.
- Groq minimum interval defaults to 15 seconds.
- Provider HTTP calls no longer perform generic three-attempt retries internally.
- Permanent 4xx provider errors trip a run-level circuit breaker.
- A provider that fails for a vacancy is not immediately called again as its reviewer.
- The full live workflow is no longer triggered on every source-code push.

## Analysis flow

```
deterministic capture + scoring
          |
          v
Groq GPT-OSS 20B
          |
          +---- clear result ----------> final policy gate
          |
          +---- borderline/high-risk
                      |
                      v
             Gemini Flash-Lite
                      |
                      v
             conservative consensus

Groq failure ----------> Gemini fallback
```

## Future third provider

Cloudflare Workers AI is a reasonable future third failure domain, but it adds account/token setup and is unnecessary while Groq + Gemini remain healthy. OpenRouter free routing is better treated as emergency capacity rather than the primary production dependency.
