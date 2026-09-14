# Implementation plan / operating model

## Goal
Find realistic Republic of Ireland civil-engineering roles for an experienced India-based highway/infrastructure engineer, rank them for professional fit and relocation feasibility, and email only new high-quality matches daily.

## Architecture
Discover -> normalize -> cross-source dedupe -> deterministic hard filters -> permit-aware profile scoring -> AI adjudication for ambiguous roles -> rank -> notify -> persist content-hash state.

## Precision rules
- experienced roles only; graduate/intern/apprentice roles are rejected;
- explicit no-sponsorship/existing-right-to-work language is a hard reject;
- Northern Ireland is excluded because it uses the UK immigration system;
- highways/roads/transport/site/resident/civil-design roles receive the strongest fit scores;
- generic and senior titles receive contextual/AI review instead of title-only acceptance;
- mandatory Chartered status or mandatory Irish experience blocks a final match;
- experience requirements above the candidate profile are capped/penalised;
- contracts under 12 months are rejected as poor first-relocation targets;
- 12-23 month offers are not treated as Critical Skills-compatible;
- salary is used only from explicit salary/remuneration context so project values cannot be mistaken for pay;
- public-sector pay-scale roles are not automatically rejected because employment-permit remuneration treatment can differ.

## Verified production source baseline
Enabled after live GitHub Actions validation:
- LocalGovernmentJobs
- JobsIreland
- Roughan O'Donovan / HireHive
- DBFL / HireHive
- AtkinsRéalis Ireland
- Arup Ireland
- LinkedIn alert email ingestion
- Indeed alert email ingestion

Disabled until dedicated adapters are independently validated:
- IrishJobs
- Jobs.ie
- PublicJobs
- Nicholas O'Dwyer

A disabled source must not be counted as coverage.

## Reliability rules
- one failed source does not abort the whole run;
- a minimum number of productive sources is required before notification;
- malformed vacancy URLs are rejected before detail fetching;
- each web source has a processing time budget;
- transient HTTP/429 failures retry and honor Retry-After;
- Groq JSON-schema generation failures retry in JSON-object mode with the same application-side validation;
- permanent AI provider/model/auth failures disable AI for the rest of the run;
- ambiguous AI-dependent classifications become provisional and retry when AI recovers;
- unchanged vacancies are not reclassified;
- profile or policy-version changes force reclassification;
- volatile posting-age text is excluded from the notification content hash;
- state is persisted before email and exact content hashes are marked notified only after SMTP success;
- SMTP retries three times;
- stale job state is pruned after 90 days.

## Pre-merge verification gate
A push to the build branch must pass unit/regression tests and a secret-backed dry run that validates public sources, Gmail IMAP, Groq and SMTP authentication without sending mail or writing state.


## JobsIreland dedicated adapter

JobsIreland is intentionally excluded from the generic Requests-first board adapter.

The dedicated `JobsIrelandSource` is browser-first because GitHub-hosted runners repeatedly experienced long Requests timeouts even though the site itself remained usable in Chromium. The adapter:

- starts Chromium once per JobsIreland sweep;
- reuses one browser context across all searches;
- searches the configured civil/highway/site/resident/project/transport/infrastructure role families;
- extracts numeric vacancy IDs from rendered links;
- deduplicates vacancy IDs across overlapping searches before visiting details;
- parses JSON-LD JobPosting data when available, with rendered-page fallback;
- has global search and detail budgets so one source cannot monopolize the workflow;
- reports partial results if the time budget is reached rather than hanging the full daily run.

The old generic JobsIreland configuration remains disabled as an explicit record of why it was replaced.
