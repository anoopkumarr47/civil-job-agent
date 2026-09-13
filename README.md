# Ireland Civil Job Agent

Daily, precision-first discovery of Republic of Ireland civil-engineering jobs for an experienced India-based highway/infrastructure engineer seeking relocation.

## Candidate fit encoded

The profile is derived from the supplied CV but deliberately excludes personal contact details. It targets a B.Tech Civil Engineer with 6.5+ years of experience, especially highways/roads/infrastructure, Civil 3D/AutoCAD, horizontal/vertical alignment, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant coordination.

## Production source coverage

Enabled sources now include:

- LocalGovernmentJobs
- JobsIreland across civil/site/highway/roads/resident/project/transportation/setting-out/infrastructure searches
- Roughan O'Donovan / HireHive
- DBFL / HireHive
- AtkinsRéalis Ireland careers
- Arup Ireland careers
- AECOM Ireland through the SmartRecruiters public Posting API
- Egis Ireland through the SmartRecruiters public Posting API
- LinkedIn daily job-alert emails through Gmail IMAP
- Indeed daily job-alert emails through Gmail IMAP

The generic IrishJobs, Jobs.ie and PublicJobs adapters remain disabled because their current automated endpoints were not reliable enough for production. Nicholas O'Dwyer also remains disabled until a dedicated current-vacancies adapter is implemented and verified.

This is broad coverage, not a claim that every civil job published anywhere in Ireland is captured. The agent reports source health/counts so missing coverage is visible rather than hidden.

## Ranking

Each vacancy is assessed for professional fit, experience fit, CV skill overlap, hard blockers such as graduate/no-sponsorship roles, Republic of Ireland location, Critical Skills/General Employment Permit plausibility, salary when available, relocation support and contract duration.

Current configured thresholds are EUR 40,909 for the standard relevant-degree Critical Skills route and EUR 36,605 for the normal General Employment Permit threshold. Contracts under 12 months are rejected as poor first-relocation targets; 12–23 month offers are not presented as Critical Skills-compatible.

## Required GitHub Actions secrets

Existing:
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `GROQ_API_KEY`

Add for multi-provider distribution:
- `GEMINI_API_KEY`

Recommended Actions variables:
- `AI_PRIMARY_MODEL=openai/gpt-oss-20b` (default)
- `AI_MODEL=openai/gpt-oss-120b` (Groq escalation/second-opinion model)
- `GEMINI_MODEL=gemini-3.5-flash-lite` (default)

No separate IMAP secret is required; Gmail address/app password are reused for IMAP and SMTP.

## AI behavior

The agent no longer reduces coverage merely to save Groq quota.

1. deterministic logic hard-rejects only obvious bad fits/blockers;
2. every plausible civil/infrastructure role with a sufficient deterministic score receives AI review;
3. vacancy input is compressed into a decision-relevant evidence packet instead of sending the first 9,000 characters;
4. when both providers are configured, first-pass reviews are deterministically split between Groq and Gemini;
5. borderline/high-risk decisions receive an independent second-provider opinion;
6. provider disagreement is consolidated conservatively so a plausible candidate is retained for manual review rather than silently dropped;
7. Groq calls are paced and token-reset headers are respected;
8. unchanged jobs reuse state and are not reclassified every day.

Groq uses structured JSON Schema with JSON-object recovery. Gemini uses structured JSON output and the same application-side Assessment validation.

Production uses `AI_REQUIRED=false`, so an external provider outage does not crash the daily job sweep. AI-dependent vacancies can remain provisional and retry later.

## LinkedIn / Indeed

LinkedIn and Indeed are supplemental alert-email feeds. The agent does not store browser cookies or automate logged-in LinkedIn sessions.

Create daily Ireland alerts for:
Highway Engineer, Road Design Engineer, Civil Design Engineer, Site Engineer, Resident Engineer, Project Engineer, Civil Engineer, Infrastructure Engineer, Transportation Engineer and Setting Out Engineer.

## Validation

- CI runs the regression suite.
- The real `Ireland Civil Job Agent` workflow runs on pushes to the build branch in forced dry-run mode.
- That path uses the same discovery and ranking entry point as the scheduled production run.
- Dry-run sends no job email and writes no state.

## Daily workflow

Scheduled at 06:15 UTC daily. Manual workflow dispatch supports `dry_run=true` for safe end-to-end validation.
