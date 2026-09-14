# Ireland Civil Job Agent

Production-oriented discovery, ranking and notification for Republic of Ireland civil-engineering jobs, tailored to an experienced India-based highway/infrastructure engineer seeking relocation.

## Design goals

The system is optimized for two competing requirements:

- **high recall**: retain genuine civil opportunities even when the title is generic, multidisciplinary or outside the strongest highway niche;
- **high precision**: do not treat generic terms such as `Infrastructure Engineer`, `Project Engineer` or `Design Engineer` as civil unless the vacancy evidence supports physical/civil infrastructure.

No scraper can guarantee capture of every vacancy on the internet because employers and job boards change, block automation, or publish roles privately. This project therefore uses multiple independent source types, logs source health, preserves ambiguous candidates for review, and fails closed when source coverage is too weak.

## Candidate profile

The checked-in profile excludes personal contact details and targets a B.Tech Civil Engineer with 6.5+ years of experience, strongest in highways/roads/transport infrastructure, Civil 3D/AutoCAD, alignment design, DPRs, plans/profiles/cross-sections, estimates/tenders/BOQ, site supervision, QA/QC and contractor/consultant/utility coordination.

## Civil-domain precision

A shared relevance layer is used by employer boards, SmartRecruiters, email alerts and final scoring.

Strong civil signals include civil engineering, highways/roads, drainage/water/wastewater, earthworks, rail civil works, setting out, transport infrastructure, public realm, pavement, construction/site supervision and Civil 3D.

Strong non-civil signals include AWS/Azure/GCP, Kubernetes, Terraform, DevOps, cloud/network infrastructure, Windows/Linux server administration, Active Directory, VMware, cybersecurity, software development and site reliability engineering.

Generic titles are deliberately treated as ambiguous until the description establishes the domain. Clearly non-civil technology roles are rejected before AI calls.

## Source coverage

Configured production sources include:

- LocalGovernmentJobs
- JobsIreland via a dedicated browser-first paginated search adapter
- Roughan O'Donovan / HireHive
- DBFL / HireHive
- AtkinsRéalis Ireland
- Arup Ireland
- AECOM via SmartRecruiters
- Egis via SmartRecruiters
- TOBIN
- SYSTRA
- Mott MacDonald via a paginated SAP SuccessFactors adapter
- LinkedIn job-alert email ingestion
- Indeed job-alert email ingestion

IrishJobs, Jobs.ie, PublicJobs and Nicholas O'Dwyer generic adapters remain disabled where live automation has not been reliable enough. A disabled source is not counted as coverage.

JobsIreland searches civil/site/highway/roads/resident/project/transport/setting-out/drainage/water/wastewater/structural/geotechnical/traffic/pavement/rail/permanent-way/utilities/inspection families. Specialized civil roles are no longer discarded merely by title; fit is handled later by scoring and AI review.

## Matching pipeline

```text
discover
  -> normalize
  -> exact-URL dedupe
  -> conservative cross-source duplicate merge
  -> location / sponsorship / early-career hard gates
  -> civil-domain classification
  -> permit-aware deterministic scoring
  -> Groq adjudication for plausible roles
  -> Gemini fallback / independent review where useful
  -> conservative final policy gate
  -> notify only new non-provisional matches
  -> persist state
```

Distinct requisitions with the same title/company/location are preserved. Cross-source duplicates are merged only when their normalized identity fields match and their descriptions are strongly similar.

## AI providers

Production uses two independent providers:

1. Groq `openai/gpt-oss-20b` as primary.
2. Gemini `gemini-3.5-flash-lite` as fallback and independent reviewer.

Provider output is strict-schema validated. Permanent provider/auth/model 4xx errors trip a run-level circuit breaker. Rate-limit/provider failures do not automatically turn uncertain classifications into notifications; those assessments remain provisional and are retried later.

## Required GitHub Actions secrets

- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_TO`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`

Recommended Actions variables:

- `GROQ_MODEL=openai/gpt-oss-20b`
- `GEMINI_MODEL=gemini-3.5-flash-lite`

Legacy `AI_MODEL` is still accepted as a fallback for `GROQ_MODEL`.

## Gemini key setup

Create a Gemini API key in Google AI Studio and save it as the repository Actions secret `GEMINI_API_KEY`:

`Repository -> Settings -> Secrets and variables -> Actions -> New repository secret`

Never commit API keys or store them as repository variables.

## Schedule and deployment

The workflow is configured for 08:00 and 20:00 India Standard Time:

```yaml
cron: "30 2,14 * * *"
```

GitHub scheduled workflows execute only from the repository default branch. Therefore the production implementation and `.github/workflows/daily.yml` must be merged to `main` (the current default branch) before the twice-daily schedule is actually active.

Ordinary code pushes use the lightweight CI workflow. A live source/AI validation run is intentionally manual through `workflow_dispatch` so free-tier AI quotas are not consumed on every commit.

## State and notification safety

State version 3 uses the canonical posting URL as the durable posting identity. Version-2 state is migrated lazily so already-notified jobs are not resent after the upgrade.

Dry runs load existing state read-only. They never send email or write state, while unchanged postings avoid unnecessary AI reclassification.

Email is sent only after source-health checks pass. State is saved before notification, and notification hashes are recorded only after SMTP success.

## Manual production validation

After secrets are configured and the code is on the default branch:

1. Open **Actions -> Ireland Civil Job Agent -> Run workflow**.
2. Choose `dry_run=true`.
3. Confirm AI and SMTP validation steps succeed.
4. Inspect source-health counts and any source errors.
5. Inspect `AI calls by model`, provisional count and dry-run matches.
6. Spot-check generic titles such as Infrastructure Engineer to confirm IT/cloud roles are excluded and physical-infrastructure roles are retained.
7. Run a normal manual workflow only after the dry-run is clean.

## Permit policy

Employment-permit figures are configuration, not guarantees. The candidate profile records the date on which the configured thresholds were reviewed. Changes to permit policy must bump either the profile version or scoring policy version so persisted jobs are re-evaluated.
