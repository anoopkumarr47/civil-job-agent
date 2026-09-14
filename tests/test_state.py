import json

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


def test_v2_state_is_read_and_lazily_migrated(tmp_path):
    path = tmp_path / "state.json"
    job = Job("test", "https://x/1", "Civil Engineer", "A", "Dublin", "v1")
    raw = {
        "version": 2,
        "updated_at": None,
        "jobs": {
            job.legacy_identity_key: {
                "identity_key": job.legacy_identity_key,
                "url": job.canonical_url,
                "source": job.source,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "content_hash": job.content_hash,
                "profile_version": "p1",
                "policy_version": POLICY_VERSION,
                "assessment": assessment().to_dict(),
                "first_seen": "2026-09-01T00:00:00+00:00",
                "last_seen": "2026-09-01T00:00:00+00:00",
                "notified_hash": job.content_hash,
                "notified_at": "2026-09-01T00:00:00+00:00",
            }
        },
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    store = StateStore(str(path))
    store.load()
    assert not store.needs_review(job, "p1", POLICY_VERSION, True)
    assert store.is_notified(job)
    store.record(job, assessment(), "p1", POLICY_VERSION)
    assert job.identity_key in store.data["jobs"]
    assert job.legacy_identity_key not in store.data["jobs"]
