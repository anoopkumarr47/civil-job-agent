# Ireland Civil Job Agent

Daily, precision-first discovery of Republic of Ireland civil-engineering jobs for an experienced India-based highway/infrastructure engineer seeking relocation.

## Candidate fit encoded

The profile is derived from the supplied CV but excludes personal contact details. It targets a B.Tech Civil Engineer with 6.5+ years of experience, especially highways/roads/infrastructure, Civil 3D/AutoCAD, alignment design, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant coordination.

## Production source coverage

Enabled sources include LocalGovernmentJobs, JobsIreland, Roughan O'Donovan, DBFL, AtkinsRéalis, Arup, AECOM, Egis, TOBIN, SYSTRA, LinkedIn alerts and Indeed alerts. IrishJobs, Jobs.ie, PublicJobs and Nicholas O'Dwyer remain disabled until dedicated reliable adapters are available.

## AI architecture

The production AI waterfall uses two independent free-tier providers:

1. deterministic rules reject obvious non-matches and score plausible jobs;
2. Groq `openai/gpt-oss-20b` is the primary classifier;
3. Gemini `gemini-3.5-flash-lite` is the independent fallback/reviewer;
4. borderline/high-risk decisions can receive a second-provider review;
5. outputs are schema-validated and consolidated conservatively;
6. unchanged jobs reuse persisted state instead of being reclassified every run.

Cerebras configuration fields are retained only for backwards compatibility. Cerebras is no longer part of the active provider waterfall.

## Required GitHub Actions secrets

- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`

Recommended Actions variables:

- `AI_MODEL=openai/gpt-oss-20b`
- `GEMINI_MODEL=gemini-3.5-flash-lite`

## Gemini key setup

Create a Gemini API key in Google AI Studio and store it in this repository as an Actions secret named `GEMINI_API_KEY`.

GitHub path:

`Repository -> Settings -> Secrets and variables -> Actions -> New repository secret`

Name: `GEMINI_API_KEY`

Value: the key copied from Google AI Studio.

New Gemini keys created in AI Studio are authorization keys. Do not commit the key or place it in repository variables.

## Schedule

The production workflow runs twice daily at 08:00 and 20:00 India Standard Time:

```yaml
cron: "30 2,14 * * *"
```

The heavy discovery/classification workflow no longer runs on every push. Ordinary pushes are covered by the lightweight CI test workflow; use `workflow_dispatch` when you intentionally want a live dry-run.

## Manual test

After configuring both AI secrets:

1. GitHub -> Actions -> Ireland Civil Job Agent.
2. Choose **Run workflow**.
3. Set `dry_run=true`.
4. Confirm **Validate AI configuration** succeeds.
5. Inspect **Run actual job agent** for source counts, `AI calls by model`, final matches and `Dry run complete`.

Dry-run sends no notification email and writes no state.

## JobsIreland reliability

JobsIreland uses a dedicated browser-first adapter with one Chromium session, vacancy-ID deduplication, canonical detail URLs and global search/detail time budgets. This avoids the repeated Requests timeout pattern previously seen on GitHub-hosted runners.
