# Ireland Civil Job Agent

Daily, precision-first discovery of Republic of Ireland civil-engineering jobs for an experienced India-based highway/infrastructure engineer seeking relocation.

## Candidate fit encoded

The profile is derived from the supplied CV but deliberately excludes personal contact details. It targets a B.Tech Civil Engineer with 6.5+ years of experience, especially highways/roads/infrastructure, Civil 3D/AutoCAD, horizontal/vertical alignment, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant coordination.

## Sources

- LocalGovernmentJobs
- JobsIreland
- IrishJobs
- Jobs.ie
- PublicJobs
- selected direct employer/ATS pages including Roughan O'Donovan, DBFL and AtkinsRealis
- LinkedIn daily job-alert emails through Gmail IMAP
- Indeed daily job-alert emails through Gmail IMAP

LinkedIn/Indeed accounts are never automated or logged into by the scraper. The agent reads normal alert emails using the same Gmail App Password used for SMTP.

## Ranking

Each vacancy is assessed for professional fit, experience fit, CV skill overlap, hard blockers such as graduate/no-sponsorship roles, Republic of Ireland location, Critical Skills/General Employment Permit plausibility, salary when available, relocation support and contract duration.

Current configured thresholds are EUR 40,909 for the standard relevant-degree Critical Skills route and EUR 36,605 for the general General Employment Permit threshold. These are configuration values and should be reviewed when government rules change.

## Required GitHub Actions secrets

- `EMAIL_ADDRESS` — Gmail account used to read alerts and send the digest
- `EMAIL_PASSWORD` — Google App Password, not the normal Gmail password
- `EMAIL_TO` — digest recipient
- `GROQ_API_KEY` — separate Groq API key for this project

Recommended Actions variable:

- `AI_MODEL=openai/gpt-oss-120b`

No separate IMAP secret is required; the Gmail address/app password are reused for IMAP and SMTP.

## LinkedIn / Indeed setup

Create daily Ireland alerts to `EMAIL_ADDRESS` for searches such as Highway Engineer, Road Design Engineer, Civil Design Engineer, Site Engineer, Resident Engineer, Project Engineer, Civil Engineer, Infrastructure Engineer, Transportation Engineer and Setting Out Engineer.

## Run locally

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
pytest
DRY_RUN=true MIN_SUCCESSFUL_SOURCES=1 python -m civil_job_agent.main
```

## Daily workflow

The scheduled GitHub Action runs at 06:15 UTC daily. A manual workflow run can be started with `dry_run=true` to discover/classify without sending mail or persisting state.
