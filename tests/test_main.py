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
