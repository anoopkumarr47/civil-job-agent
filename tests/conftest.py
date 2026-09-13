import pytest

from civil_job_agent.config import Settings


@pytest.fixture
def profile():
    import json
    from pathlib import Path
    return json.loads(Path("config/candidate_profile.json").read_text())


@pytest.fixture
def settings(tmp_path):
    return Settings(
        state_file=str(tmp_path / "state.json"),
        profile_file="config/candidate_profile.json",
        sources_file="config/sources.json",
        request_timeout=10,
        max_links_per_source=20,
        ai_api_url="https://example.invalid/chat",
        ai_api_key=None,
        ai_model="openai/gpt-oss-120b",
        ai_timeout=10,
        ai_required=False,
        email_address=None,
        email_password=None,
        email_to=None,
        dry_run=False,
        mail_lookback_days=3,
        min_successful_sources=1,
        stale_days=90,
    )
