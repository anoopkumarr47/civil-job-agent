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
