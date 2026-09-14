from dataclasses import replace

from civil_job_agent import main
from civil_job_agent.models import Job


class FakeSource:
    name = "Fake"

    def discover(self):
        return [
            Job(
                "Fake",
                "https://example/1",
                "Highway Engineer",
                "Firm",
                "Dublin, Ireland",
                "Civil 3D roads horizontal alignment",
            )
        ]


def test_dry_run_never_sends_or_persists(settings, monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    dry = replace(settings, state_file=str(path), dry_run=True)
    monkeypatch.setattr(main, "_build_sources", lambda *_: [FakeSource()])
    monkeypatch.setattr(
        main,
        "send_email",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("email called")),
    )
    assert main.run(dry) == 0
    assert not path.exists()


class EmptySource:
    name = "Empty"

    def discover(self):
        return []


def test_empty_sources_do_not_count_as_healthy_coverage(settings, monkeypatch):
    dry = replace(settings, dry_run=True)
    monkeypatch.setattr(main, "_build_sources", lambda *_: [EmptySource()])
    try:
        main.run(dry)
    except RuntimeError as exc:
        assert "produced candidate jobs" in str(exc)
    else:
        raise AssertionError("empty sources should not pass source-health gate")


def test_production_requires_mail_settings(settings, monkeypatch):
    monkeypatch.setattr(main, "_build_sources", lambda *_: [FakeSource()])
    try:
        main.run(settings)
    except RuntimeError as exc:
        assert "Production mode requires email configuration" in str(exc)
    else:
        raise AssertionError("production without mail settings should fail")


def test_build_sources_uses_dedicated_jobsireland(settings):
    from civil_job_agent.sources import JobsIrelandSource

    cfg = {
        "web_sources": [
            {
                "name": "JobsIreland",
                "enabled": False,
                "search_urls": [],
                "allowed_hosts": ["jobsireland.ie"],
                "job_link_patterns": ["job-details"],
            }
        ],
        "jobsireland_source": {
            "name": "JobsIreland",
            "enabled": True,
            "search_terms": ["civil engineer", "site engineer"],
            "max_links": 50,
        },
        "smartrecruiters_sources": [],
        "mail_sources": [],
    }

    sources = main._build_sources(settings, cfg)
    assert sum(isinstance(source, JobsIrelandSource) for source in sources) == 1
    assert [source.name for source in sources].count("JobsIreland") == 1


def test_dedupe_keeps_distinct_same_title_requisitions():
    a = Job("A", "https://a/jobs/1", "Civil Engineer", "Firm", "Dublin", "civil roads alpha requisition")
    b = Job("A", "https://a/jobs/2", "Civil Engineer", "Firm", "Dublin", "civil roads beta entirely different")
    assert len(main._dedupe([a, b])) == 2


def test_dedupe_merges_highly_similar_cross_source_posting():
    text = "Civil roads drainage site supervision contractor coordination Civil 3D permanent role"
    a = Job("A", "https://a/jobs/1", "Civil Engineer", "Firm", "Dublin", text)
    b = Job("B", "https://b/jobs/99", "Civil Engineer", "Firm", "Dublin", text + " apply now")
    result = main._dedupe([a, b])
    assert len(result) == 1
    assert "A" in result[0].source and "B" in result[0].source


def test_health_degrades_when_provisional_ratio_is_high(settings):
    from civil_job_agent.ai import AIClient
    from civil_job_agent.models import Assessment, SourceReport

    ai = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
        )
    )
    ai.providers["groq_primary"].disabled_reason = "preflight failed"
    ai.providers["groq_backup"].disabled_reason = "preflight failed"
    ai.providers["gemini"].disabled_reason = "preflight failed"
    vacancy = Job(
        "Fake",
        "https://example/1",
        "Project Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    assessments = {
        vacancy.identity_key: Assessment(
            True,
            82,
            "project_engineer",
            "critical_skills",
            "high",
            "candidate",
            provisional=True,
        )
    }
    health = main._health_payload(
        settings,
        reports=[SourceReport("Fake", 1, True)],
        jobs=[vacancy],
        assessments=assessments,
        ai=ai,
    )
    assert health["status"] == "degraded"
    assert health["provisional_ratio"] == 1.0


def test_health_is_healthy_with_one_ready_provider(settings):
    from civil_job_agent.ai import AIClient
    from civil_job_agent.models import Assessment, SourceReport

    ai = AIClient(replace(settings, gemini_api_key="gemini-key"))
    vacancy = Job(
        "Fake",
        "https://example/1",
        "Highway Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    assessments = {
        vacancy.identity_key: Assessment(
            True,
            95,
            "highway_engineer",
            "critical_skills",
            "high",
            "fit",
            source="deterministic",
        )
    }
    health = main._health_payload(
        settings,
        reports=[SourceReport("Fake", 1, True)],
        jobs=[vacancy],
        assessments=assessments,
        ai=ai,
    )
    assert health["status"] == "healthy"
    assert health["provisional"] == 0


def test_dry_run_clear_match_survives_without_ai(settings, monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    health_path = tmp_path / "health.json"
    dry = replace(
        settings,
        state_file=str(path),
        run_health_file=str(health_path),
        dry_run=True,
        groq_api_key=None,
        gemini_api_key=None,
    )
    monkeypatch.setattr(main, "_build_sources", lambda *_: [FakeSource()])
    assert main.run(dry) == 0

    import json

    health = json.loads(health_path.read_text(encoding="utf-8"))
    assert health["status"] == "healthy"
    assert health["provisional"] == 0


def test_health_remains_healthy_with_two_independent_vendors(settings):
    from civil_job_agent.ai import AIClient
    from civil_job_agent.models import SourceReport

    ai = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            gemini_api_key="gemini-key",
        )
    )
    ai.providers["gemini"].disabled_reason = "daily quota exhausted"
    health = main._health_payload(
        settings,
        reports=[SourceReport("Fake", 1, True)],
        jobs=[],
        assessments={},
        ai=ai,
    )
    assert health["status"] == "healthy"
    assert health["operational_ai_vendors"] == ["cloudflare", "groq"]


def test_health_degrades_when_only_one_vendor_remains(settings):
    from civil_job_agent.ai import AIClient
    from civil_job_agent.models import SourceReport

    ai = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            gemini_api_key="gemini-key",
        )
    )
    ai.providers["cloudflare"].disabled_reason = "daily quota exhausted"
    ai.providers["gemini"].disabled_reason = "daily quota exhausted"
    health = main._health_payload(
        settings,
        reports=[SourceReport("Fake", 1, True)],
        jobs=[],
        assessments={},
        ai=ai,
    )
    assert health["status"] == "degraded"
    assert health["operational_ai_vendors"] == ["groq"]
    assert any("vendor redundancy" in reason for reason in health["reasons"])


def test_health_does_not_degrade_for_temporary_provider_cooldown(settings):
    import time
    from civil_job_agent.ai import AIClient
    from civil_job_agent.models import SourceReport

    ai = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key=None,
        )
    )
    ai.providers["groq_primary"].cooldown_until = time.monotonic() + 2

    health = main._health_payload(
        settings,
        reports=[SourceReport("Fake", 1, True)],
        jobs=[],
        assessments={},
        ai=ai,
    )
    assert health["status"] == "healthy"
    assert health["providers"]["groq_primary"]["operational"]
    assert not health["providers"]["groq_primary"]["ready"]
    assert health["providers"]["groq_backup"]["ready"]
