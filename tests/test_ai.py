import pytest

from civil_job_agent.ai import AIClient, compact_job_evidence


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


def test_compact_evidence_limits_size_and_keeps_requirements():
    from civil_job_agent.models import Job

    text = (
        "Introduction text. " * 80
        + "Minimum 5 years experience in civil roads. "
        + "Civil 3D and AutoCAD are required. "
        + "No visa sponsorship is available. "
        + "Salary €55,000 per annum. "
        + ("Generic company text. " * 150)
    )
    vacancy = Job("test", "https://example/1", "Civil Engineer", "Firm", "Dublin", text)
    evidence = compact_job_evidence(vacancy, 1200)

    assert len(evidence) <= 1200
    assert "Minimum 5 years experience" in evidence
    assert "No visa sponsorship" in evidence


def test_primary_model_does_not_escalate_clear_result():
    from civil_job_agent.models import Assessment, Job

    vacancy = Job("test", "https://example/1", "Civil Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 92, "civil_engineer", "critical_skills_plausible", "high", "fit")
    primary = Assessment(True, 94, "civil_engineer", "critical_skills", "high", "fit", source="ai-refined")

    assert not AIClient._needs_escalation(vacancy, preliminary, primary, 76)


def test_borderline_result_escalates():
    from civil_job_agent.models import Assessment, Job

    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 84, "project_engineer", "critical_skills_plausible", "high", "fit")
    primary = Assessment(True, 78, "project_engineer", "critical_skills", "high", "fit", source="ai-refined")

    assert AIClient._needs_escalation(vacancy, preliminary, primary, 76)


def test_refine_uses_primary_then_escalation(settings, monkeypatch):
    from dataclasses import replace
    from civil_job_agent.models import Assessment, Job

    configured = replace(settings, ai_api_key="test-key")
    client = AIClient(configured)
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 84, "project_engineer", "critical_skills_plausible", "high", "fit")

    calls = []

    def fake_call(job, assessment, model):
        calls.append(model)
        if model == "openai/gpt-oss-20b":
            return Assessment(True, 78, "project_engineer", "critical_skills", "high", "primary", source="ai-refined")
        return Assessment(True, 88, "project_engineer", "critical_skills", "high", "escalated", source="ai-refined")

    monkeypatch.setattr(client, "_call_with_json_recovery", fake_call)
    result = client.refine(vacancy, preliminary, threshold=76)

    assert calls == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    assert result.score == 88
