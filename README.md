# Ireland Civil Job Agent

Daily, precision-first discovery of Republic of Ireland civil-engineering jobs for an experienced India-based highway/infrastructure engineer seeking relocation.

## Candidate fit encoded

The profile is derived from the supplied CV but deliberately excludes personal contact details. It targets a B.Tech Civil Engineer with 6.5+ years of experience, especially highways/roads/infrastructure, Civil 3D/AutoCAD, horizontal/vertical alignment, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant coordination.

## Verified production sources

The enabled public-source baseline is intentionally limited to sources that completed successfully from GitHub Actions during live dry-run validation:

- LocalGovernmentJobs
- JobsIreland
- Roughan O'Donovan / HireHive
- DBFL / HireHive
- AtkinsRéalis Ireland careers
- Arup Ireland careers
- LinkedIn daily job-alert emails through Gmail IMAP
- Indeed daily job-alert emails through Gmail IMAP

The generic IrishJobs, Jobs.ie and PublicJobs adapters are disabled because their current automated endpoints were not reliable enough for production. Nicholas O'Dwyer is also disabled until a dedicated current-vacancies/Networx-style adapter is implemented and verified. Disabled sources remain documented in `config/sources.json` with the reason for each decision.

LinkedIn/Indeed accounts are never logged into or browser-automated by this scraper. The agent reads normal alert emails using the same Gmail App Password used for SMTP.

## Ranking

Each vacancy is assessed for professional fit, experience fit, CV skill overlap, hard blockers such as graduate/no-sponsorship roles, Republic of Ireland location, Critical Skills/General Employment Permit plausibility, salary when available, relocation support and contract duration.

Current configured thresholds are EUR 40,909 for the standard relevant-degree Critical Skills route and EUR 36,605 for the general General Employment Permit threshold. Contract offers shorter than two years are not presented as Critical Skills-compatible, and contracts under 12 months are rejected as poor first-relocation targets.

Senior/principal/lead roles, ambiguous occupational titles, experience gaps, mandatory Chartered status and mandatory Irish-experience requirements receive stricter review.

## Required GitHub Actions secrets

- `EMAIL_ADDRESS` — Gmail account used to read alerts and send the digest
- `EMAIL_PASSWORD` — Google App Password, not the normal Gmail password
- `EMAIL_TO` — digest recipient
- `GROQ_API_KEY` — Groq API key for this project

Recommended Actions variable:

- `AI_MODEL=openai/gpt-oss-120b`

No separate IMAP secret is required; the Gmail address/app password are reused for IMAP and SMTP.

## AI behavior

Groq structured JSON Schema is the preferred response mode. If Groq returns its known JSON-generation validation error, the agent retries that vacancy in JSON-object mode and still applies the same strict application-side field/type/enum validation. Transient HTTP 429 responses honor retry delays.

Production uses `AI_REQUIRED=false`: deterministic high-confidence roles can continue during a provider outage, while AI-dependent roles remain provisional and are retried later.

## LinkedIn / Indeed setup

Create daily Ireland alerts to `EMAIL_ADDRESS` for searches such as Highway Engineer, Road Design Engineer, Civil Design Engineer, Site Engineer, Resident Engineer, Project Engineer, Civil Engineer, Infrastructure Engineer, Transportation Engineer and Setting Out Engineer.

If no recent alert emails exist, those mail sources correctly report zero candidates without failing the public-source sweep.

## Validation

The branch CI includes:
- the full regression test suite;
- live public-source discovery;
- real Gmail IMAP authentication and alert scanning;
- real Groq adjudication;
- SMTP authentication without sending mail.

The integration run is always `DRY_RUN=true`, so it sends no job email and persists no state.

## Run locally

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
pytest
DRY_RUN=true MIN_SUCCESSFUL_SOURCES=1 python -m civil_job_agent.main
```

## Daily workflow

The scheduled GitHub Action runs at 06:15 UTC daily. A manual workflow run can be started with `dry_run=true` to discover/classify without sending mail or persisting state.
