# Production operating model

## Objective

Discover realistic Republic of Ireland civil-engineering opportunities with broad coverage, reject unrelated engineering/IT roles, rank candidate fit and relocation feasibility, and notify only new high-confidence opportunities.

## Recall strategy

- search multiple independent employer/job-board sources plus LinkedIn and Indeed alert email;
- retain generic titles when the description is ambiguous rather than dropping them at discovery time;
- explicitly cover highways, roads, transportation, site/resident/project engineering, setting out, drainage, water/wastewater, rail/permanent way, traffic, pavement, structural, geotechnical, utilities, public realm and site-development families;
- do not source-filter structural/geotechnical/bridge roles solely because they are outside the strongest CV niche;
- preserve distinct requisitions even if title/company/location are identical;
- use URL identity plus conservative content-similarity merging for duplicates;
- log productive source counts and refuse notification if too few sources produce candidates.

## Precision strategy

- Republic of Ireland only; Northern Ireland is rejected;
- graduate/intern/apprentice/placement roles are rejected;
- explicit no-sponsorship/existing-right-to-work blockers are rejected;
- generic titles do not establish civil domain by themselves;
- cloud/network/software/data/DevOps infrastructure signals are a hard non-civil domain gate;
- physical/civil evidence such as roads, drainage, earthworks, rail, construction/site works, Civil 3D, alignment, pavement and public realm establishes civil domain;
- mandatory Chartered status and mandatory Irish experience block a final match;
- excessive experience and specialist requirements reduce fit rather than causing indiscriminate source-level exclusion;
- salary is parsed only from explicit compensation context;
- short contracts are treated conservatively for first-time relocation.

## AI architecture

Groq GPT-OSS 20B is the primary adjudicator. Gemini Flash-Lite is an independent fallback/reviewer. Both must conform to the same strict output schema.

A provider that returns a permanent API/auth/model error is disabled for the remainder of the run. Provider outages create provisional assessments rather than unsafe notifications.

Two-provider disagreement is resolved conservatively: an ambiguous deterministic candidate cannot become a final match on a one-versus-one AI split; a strong deterministic civil candidate can be retained when one reviewer provides a strong positive assessment.

## Source adapters

### JobsIreland

Browser-first, one Chromium session per sweep, multiple civil search families, numeric vacancy-ID dedupe, JSON-LD/detail parsing, and global search/detail budgets.

### SmartRecruiters

Uses the public Posting API. Non-target postings do not consume the candidate cap, so later civil roles remain discoverable.

### SAP SuccessFactors

Paginates the employer job index and filters by Republic of Ireland location plus plausible engineering title before detail fetches. Mott MacDonald is configured through this adapter.

### Generic employer boards

Requests-first discovery with Chromium fallback. Detail pages prefer JobPosting JSON-LD and then rendered HTML. The shared civil-domain relevance gate runs before a candidate reaches scoring.

### Email alerts

LinkedIn and Indeed alerts are read via Gmail IMAP. Alert links are restricted to allowed hosts and pass the same shared relevance gate.

## State and notification

- state v3 identity = canonical posting URL;
- v2 state remains readable and migrates lazily;
- content changes, profile-version changes and scoring-policy changes force review;
- provisional assessments retry when AI becomes available;
- dry runs load state read-only;
- notification hashes prevent repeat email;
- SMTP retries three times;
- stale state is pruned after 90 days.

## Production deployment gate

1. Regression CI must pass.
2. Groq, Gemini and Gmail secrets must be present.
3. A manual dry-run must show healthy source counts and sensible matches.
4. The workflow must exist on the repository default branch, because GitHub schedules execute only from the default branch.
5. Only after the dry-run is clean should a non-dry manual run be used to validate state persistence and notification.
