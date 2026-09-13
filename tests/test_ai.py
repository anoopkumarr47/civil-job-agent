import pytest

from civil_job_agent.ai import AIClient


def valid():
    return {
        "matched": True,
        "score": 91,
        "role_family": "civil engineer",
        "permit_path": "critical_skills",
        "relocation_fit": "high",
        "reason": "Strong fit.",
        "strengths": ["roads"],
        "gaps": [],
    }


def test_ai_boolean_is_strict():
    data = valid()
    data["matched"] = "false"
    with pytest.raises(ValueError, match="JSON boolean"):
        AIClient._validate(data)


def test_ai_score_range_is_strict():
    data = valid()
    data["score"] = 101
    with pytest.raises(ValueError, match="score"):
        AIClient._validate(data)


def test_schema_generation_error_is_retryable():
    assert AIClient._schema_generation_error('{"code":"json_validate_failed","message":"Failed to validate JSON"}')
    assert not AIClient._schema_generation_error("invalid API key")


def test_transient_ai_exhaustion_becomes_provisional_in_production(settings, monkeypatch):
    from dataclasses import replace
    import requests

    from civil_job_agent.models import Assessment, Job

    configured = replace(settings, ai_api_key="test-key", ai_required=False)
    client = AIClient(configured)

    response = requests.Response()
    response.status_code = 429
    response._content = b'{"error":{"message":"rate limit"}}'
    error = requests.HTTPError("429 rate limit", response=response)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(client, "_call", fail)
    preliminary = Assessment(
        True, 85, "project_engineer", "critical_skills", "high", "candidate"
    )
    vacancy = Job("test", "https://example/jobs/1", "Project Engineer", "Firm", "Dublin", "civil roads")

    result = client.refine(vacancy, preliminary)
    assert result.provisional
    assert result is preliminary
