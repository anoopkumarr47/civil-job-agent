from __future__ import annotations

import logging
from collections import Counter

from .ai import AIClient
from .config import Settings, load_json
from .models import Assessment, Job, SourceReport
from .notify import send_email
from .scoring import POLICY_VERSION, preliminary_assessment, should_ai_refine
from .sources import ConfiguredWebBoard, GmailJobAlertSource
from .state import StateStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("civil-job-agent")


def _merge_duplicate(current: Job, incoming: Job) -> Job:
    richer = incoming if len(incoming.text) > len(current.text) else current
    sources = sorted(set(current.source.split(" + ") + incoming.source.split(" + ")))
    company = richer.company or current.company or incoming.company
    location = richer.location or current.location or incoming.location
    salary = richer.salary_text or current.salary_text or incoming.salary_text
    posted = richer.posted_text or current.posted_text or incoming.posted_text
    return Job(" + ".join(sources), richer.url, richer.title, company, location, richer.text, salary, posted)


def _dedupe(jobs: list[Job]) -> list[Job]:
    best: dict[str, Job] = {}
    for job in jobs:
        current = best.get(job.identity_key)
        best[job.identity_key] = job if current is None else _merge_duplicate(current, job)
    return list(best.values())


def _build_sources(settings: Settings, cfg: dict) -> list:
    sources = []
    for entry in cfg.get("web_sources", []):
        if entry.get("enabled", True):
            sources.append(ConfiguredWebBoard(entry, request_timeout=settings.request_timeout, max_links=settings.max_links_per_source))
    if settings.email_address and settings.email_password:
        for entry in cfg.get("mail_sources", []):
            if entry.get("enabled", True):
                sources.append(
                    GmailJobAlertSource(
                        name=entry["name"],
                        address=settings.email_address,
                        password=settings.email_password,
                        allowed_hosts=entry.get("allowed_hosts", []),
                        sender_contains=entry.get("sender_contains", []),
                        lookback_days=settings.mail_lookback_days,
                    )
                )
    else:
        logger.warning("Email credentials are not configured; LinkedIn/Indeed alert ingestion is disabled")
    return sources


def _summary(jobs: list[Job], assessments: dict[str, Assessment], reports: list[SourceReport]) -> None:
    by_source = Counter(job.source for job in jobs)
    matched = [a for a in assessments.values() if a.matched and not a.provisional]
    provisional = sum(1 for a in assessments.values() if a.provisional)
    logger.info("Source health: %s", {r.name: {"ok": r.ok, "jobs": r.jobs, "error": r.error[:120]} for r in reports})
    logger.info("Jobs by source after dedupe: %s", dict(sorted(by_source.items())))
    logger.info("Assessments=%s final_matches=%s provisional=%s", len(assessments), len(matched), provisional)


def run(settings: Settings) -> int:
    profile = load_json(settings.profile_file)
    sources_cfg = load_json(settings.sources_file)
    state = StateStore(settings.state_file)
    if settings.dry_run:
        logger.info("DRY RUN: state will not be loaded/written and email will not be sent")
    else:
        state.load()

    sources = _build_sources(settings, sources_cfg)
    jobs_raw: list[Job] = []
    reports: list[SourceReport] = []
    for source in sources:
        try:
            discovered = source.discover()
            jobs_raw.extend(discovered)
            reports.append(SourceReport(source.name, len(discovered), True))
        except Exception as exc:
            logger.exception("Source failed: %s", source.name)
            reports.append(SourceReport(source.name, 0, False, str(exc)))

    successful_sources = sum(1 for report in reports if report.ok)
    if successful_sources < settings.min_successful_sources:
        raise RuntimeError(
            f"Only {successful_sources} source(s) completed successfully; minimum is {settings.min_successful_sources}. "
            "Refusing to send a misleading incomplete daily report."
        )

    jobs = _dedupe(jobs_raw)
    logger.info("Collected %s raw and %s unique candidate jobs", len(jobs_raw), len(jobs))
    ai = AIClient(settings)
    profile_version = str(profile["profile_version"])

    for job in jobs:
        if not state.needs_review(job, profile_version, POLICY_VERSION, ai.available):
            state.touch(job)
            continue
        assessment = preliminary_assessment(job, profile)
        if should_ai_refine(assessment):
            assessment = ai.refine(job, assessment)
        state.record(job, assessment, profile_version, POLICY_VERSION)

    assessments: dict[str, Assessment] = {}
    matches: list[tuple[Job, Assessment]] = []
    for job in jobs:
        assessment = state.assessment_for(job, profile_version, POLICY_VERSION)
        if not assessment:
            continue
        assessments[job.identity_key] = assessment
        if assessment.matched and not assessment.provisional and not state.is_notified(job):
            matches.append((job, assessment))

    matches.sort(key=lambda item: (-item[1].score, item[0].title.casefold()))
    _summary(jobs, assessments, reports)

    if settings.dry_run:
        for job, assessment in matches:
            logger.info(
                "DRY MATCH %s/100 | %s | %s | %s | %s | %s",
                assessment.score, job.title, job.company, job.location, assessment.permit_path, job.url,
            )
        logger.info("Dry run complete: %s new match(es); no email and no state persistence", len(matches))
        return 0

    removed = state.prune(settings.stale_days)
    if removed:
        logger.info("Pruned %s stale state record(s)", removed)
    state.save()

    if matches:
        send_email(matches, settings)
        for job, _ in matches:
            state.mark_notified(job)
        state.save()
    logger.info("New notifications: %s", len(matches))
    return 0


def cli() -> None:
    raise SystemExit(run(Settings.from_env()))


if __name__ == "__main__":
    cli()
