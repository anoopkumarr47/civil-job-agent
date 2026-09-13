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
- generic Project Engineer / Design Engineer roles require stronger evidence and AI review;
- mandatory Chartered/Irish-experience requirements are penalised;
- salary is used when present, but public-sector pay-scale roles are not automatically rejected because employment-permit rules have public-sector remuneration treatment.

## Reliability rules
- one failed source does not abort the whole run;
- too few successful sources aborts notification to avoid a misleading incomplete digest;
- transient HTTP/429 failures retry;
- permanent AI provider/model failures disable AI for the rest of the run;
- ambiguous AI-dependent classifications become provisional and retry when AI recovers;
- unchanged vacancies are not reclassified;
- profile or policy-version changes force reclassification;
- state is persisted before email and exact content hashes are marked notified only after SMTP success;
- SMTP retries three times;
- stale job state is pruned after 90 days.

## Source evolution
Current production baseline includes the major Irish boards, LocalGovernmentJobs, PublicJobs, selected direct employer/ATS pages, plus LinkedIn/Indeed alerts through Gmail. The source config is intentionally data-driven so more employer career pages can be added without changing the classifier.
