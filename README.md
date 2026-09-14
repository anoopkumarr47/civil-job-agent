# Ireland Civil Job Agent

Daily, precision-first discovery of Republic of Ireland civil-engineering jobs for an experienced India-based highway/infrastructure engineer seeking relocation.

## Candidate fit encoded

The profile is derived from the supplied CV but excludes personal contact details. It targets a B.Tech Civil Engineer with 6.5+ years of experience, especially highways/roads/infrastructure, Civil 3D/AutoCAD, alignment design, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant coordination.

## Production source coverage

Enabled sources include:

- LocalGovernmentJobs
- JobsIreland through a dedicated browser-first, single-session adapter across civil/site/highway/roads/resident/project/transportation/setting-out/infrastructure/construction/drainage/water/assistant-engineer/civil-inspector searches
- Roughan O'Donovan / HireHive
- DBFL / HireHive
- AtkinsRéalis Ireland careers
- Arup Ireland careers
- AECOM Ireland via SmartRecruiters public Posting API
- Egis Ireland via SmartRecruiters public Posting API
- TOBIN direct careers
- SYSTRA direct careers with explicit-location validation
- LinkedIn daily job-alert emails via Gmail IMAP
- Indeed daily job-alert emails via Gmail IMAP

IrishJobs, Jobs.ie and PublicJobs generic adapters remain disabled because their current automated endpoints were not reliable enough. Nicholas O'Dwyer remains disabled until a dedicated current-vacancies adapter is verified.

This is broad coverage, not a claim that every civil vacancy published anywhere in Ireland is captured. Source health/counts are logged so coverage gaps remain visible.

## AI architecture

Cerebras is the primary reasoning provider.

1. deterministic rules hard-reject only obvious bad fits/blockers;
2. every plausible civil/infrastructure vacancy receives AI review;
3. Cerebras `gpt-oss-120b` receives a compact evidence packet (up to 6,000 decision-relevant characters);
4. routine roles use medium reasoning effort;
5. senior, borderline, permit-sensitive or requirement-gap roles use high reasoning effort;
6. Groq `openai/gpt-oss-120b` provides independent review for borderline/high-risk Cerebras decisions and acts as first fallback if Cerebras is unavailable;
7. Gemini is optional as a tertiary fallback/tie-breaker;
8. provider outputs are consolidated conservatively, preserving plausible candidates while downgrading uncertain permit conclusions;
9. unchanged jobs reuse state and are not reclassified on every run.

## Required GitHub Actions secrets

- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `CEREBRAS_API_KEY`
- `GROQ_API_KEY`

Optional:
- `GEMINI_API_KEY`

Required Gmail values:

```text
EMAIL_ADDRESS = anoopkumarremesanpillai@gmail.com
EMAIL_TO      = anoopkumarremesanpillai@gmail.com
```

`EMAIL_PASSWORD` must be the Google App Password for that Gmail account, not the normal Gmail password.

Recommended Actions variables:

- `CEREBRAS_MODEL=gpt-oss-120b`
- `AI_MODEL=openai/gpt-oss-120b`
- optional `GEMINI_MODEL=gemini-3.5-flash-lite`

## Schedule

The production workflow runs exactly twice daily:

- 08:00 India Standard Time
- 20:00 India Standard Time

IST is UTC+05:30, so GitHub Actions uses:

```yaml
cron: "30 2,14 * * *"
```

## Validation

- CI runs the regression suite.
- The real `Ireland Civil Job Agent` workflow also runs on pushes to `build/end-to-end-v1` in forced dry-run mode.
- Branch dry-runs use the same discovery/ranking entry point as production.
- Dry-run sends no job email and writes no state.
- The workflow fails early if `CEREBRAS_API_KEY` is missing.

## Manual test

After configuring secrets:

1. GitHub → Actions → Ireland Civil Job Agent.
2. Open the latest run for `build/end-to-end-v1`, or re-run the latest jobs.
3. Confirm `Validate Cerebras configuration` succeeds.
4. Confirm Gmail mailbox and SMTP validation succeeds.
5. Inspect `Run actual job agent`.
6. Look for source counts, `AI calls by model`, final matches and `Dry run complete`.

The branch run is automatically forced to `DRY_RUN=true`, so it will not email or persist state.


### JobsIreland reliability

JobsIreland does not use the generic Requests-first web-board adapter. Its dedicated adapter:

- opens one Chromium browser/context for the entire JobsIreland sweep;
- reuses that session across all configured search terms;
- extracts numeric vacancy IDs from rendered job-detail links;
- deduplicates the same vacancy across overlapping searches before detail parsing;
- uses canonical `/en-US/job-Details?id=<id>` detail URLs;
- applies one global search-time budget and one global detail-time budget;
- never performs the old two-attempt 25-second Requests timeout before browser fallback.

This avoids the repeated ~50-second-per-search timeout pattern seen from GitHub-hosted runners while preserving broad JobsIreland keyword coverage.
