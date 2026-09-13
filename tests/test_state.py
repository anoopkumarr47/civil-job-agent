from civil_job_agent.models import Assessment, Job
from civil_job_agent.scoring import POLICY_VERSION
from civil_job_agent.state import StateStore


def assessment(provisional=False):
    return Assessment(True, 90, "civil_engineer", "critical_skills", "high", "fit", provisional=provisional)


def test_content_change_forces_review(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    j1 = Job("test", "https://x/1", "Civil Engineer", "A", "Dublin", "v1")
    assert store.needs_review(j1, "p1", POLICY_VERSION, True)
    store.record(j1, assessment(), "p1", POLICY_VERSION)
    assert not store.needs_review(j1, "p1", POLICY_VERSION, True)
    j2 = Job("test", "https://x/1", "Civil Engineer", "A", "Dublin", "v2")
    assert store.needs_review(j2, "p1", POLICY_VERSION, True)


def test_provisional_retries_when_ai_recovers(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    job = Job("test", "https://x/1", "Project Engineer", "A", "Dublin", "v1")
    store.record(job, assessment(True), "p1", POLICY_VERSION)
    assert store.needs_review(job, "p1", POLICY_VERSION, True)
    assert not store.needs_review(job, "p1", POLICY_VERSION, False)


def test_policy_change_forces_review(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    job = Job("test", "https://x/1", "Civil Engineer", "A", "Dublin", "v1")
    store.record(job, assessment(), "p1", "old")
    assert store.needs_review(job, "p1", POLICY_VERSION, True)
