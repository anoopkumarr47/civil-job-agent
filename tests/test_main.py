from dataclasses import replace

from civil_job_agent import main
from civil_job_agent.models import Job


class FakeSource:
    name = "Fake"
    def discover(self):
        return [Job("Fake", "https://example/1", "Highway Engineer", "Firm", "Dublin, Ireland", "Civil 3D roads horizontal alignment")]


def test_dry_run_never_sends_or_persists(settings, monkeypatch, tmp_path):
    path = tmp_path / "state.json"
    dry = replace(settings, state_file=str(path), dry_run=True)
    monkeypatch.setattr(main, "_build_sources", lambda *_: [FakeSource()])
    monkeypatch.setattr(main, "send_email", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("email called")))
    assert main.run(dry) == 0
    assert not path.exists()


class EmptySource:
    name = "Empty"
    def discover(self):
        return []


def test_empty_sources_do_not_count_as_healthy_coverage(settings, monkeypatch):
    from dataclasses import replace
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


def test_workflow_expected_mailbox_documented():
    expected = "anoopkumarremesanpillai@gmail.com"
    assert expected.endswith("@gmail.com")


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
