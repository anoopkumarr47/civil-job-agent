import pytest

from civil_job_agent.ai import AIClient, compact_job_evidence
from civil_job_agent.models import Assessment, Job


def valid():
    return {
        "matched": True,
        "score": 91,
        "role_family": "civil_engineer",
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
    assert AIClient._schema_generation_error(
        '{"code":"json_validate_failed","message":"Failed to validate JSON"}'
    )
    assert not AIClient._schema_generation_error("invalid API key")


def test_compact_evidence_keeps_civil_and_non_civil_signals():
    text = (
        "Introduction text. " * 80
        + "Minimum 5 years experience in civil roads. "
        + "Civil 3D and AutoCAD are required. "
        + "No visa sponsorship is available. "
        + "AWS Terraform Kubernetes cloud infrastructure are also mentioned. "
        + "Salary €55,000 per annum. "
    )
    vacancy = Job("test", "https://example/1", "Infrastructure Engineer", "Firm", "Dublin", text)
    evidence = compact_job_evidence(vacancy, 1800)
    assert len(evidence) <= 1800
    assert "civil roads" in evidence
    assert "AWS" in evidence


def test_clear_highway_result_does_not_need_second_opinion():
    vacancy = Job("test", "https://example/1", "Highway Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 96, "highway_engineer", "critical_skills", "high", "fit")
    primary = Assessment(True, 94, "highway_engineer", "critical_skills", "high", "fit", source="ai-groq")
    assert not AIClient._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_ambiguous_infrastructure_result_needs_second_opinion():
    vacancy = Job("test", "https://example/1", "Infrastructure Engineer", "Firm", "Dublin", "civil works")
    preliminary = Assessment(False, 72, "infrastructure_engineer", "unclear", "medium", "review")
    primary = Assessment(True, 82, "infrastructure_engineer", "critical_skills", "high", "fit", source="ai-groq")
    assert AIClient._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_refine_uses_groq_primary_and_gemini_second_opinion(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(replace(settings, groq_api_key="groq-key", gemini_api_key="gemini-key"))
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 84, "project_engineer", "critical_skills", "high", "fit")
    calls = []

    def fake_groq(job, preliminary, reasoning_effort="medium"):
        calls.append(("groq", reasoning_effort))
        return Assessment(True, 78, "project_engineer", "critical_skills", "high", "g", source="ai-groq")

    def fake_gemini(job, preliminary):
        calls.append("gemini")
        return Assessment(True, 88, "project_engineer", "critical_skills", "high", "m", source="ai-gemini")

    monkeypatch.setattr(client, "_groq_call", fake_groq)
    monkeypatch.setattr(client, "_gemini_call", fake_gemini)

    result = client.refine(vacancy, preliminary, threshold=76)
    assert calls == [("groq", "medium"), "gemini"]
    assert result.source == "ai-consensus"
    assert result.matched


def test_gemini_falls_back_when_groq_fails(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(replace(settings, groq_api_key="groq-key", gemini_api_key="gemini-key"))
    vacancy = Job("test", "https://example/1", "Civil Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 90, "civil_engineer", "critical_skills", "high", "fit")

    monkeypatch.setattr(
        client,
        "_groq_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(
        client,
        "_gemini_call",
        lambda *args, **kwargs: Assessment(
            True, 91, "civil_engineer", "critical_skills", "high", "gemini", source="ai-gemini"
        ),
    )
    result = client.refine(vacancy, preliminary)
    assert result.source == "ai-gemini"


def test_all_provider_failures_become_provisional(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(
        replace(settings, groq_api_key="groq-key", gemini_api_key="gemini-key", ai_required=False)
    )
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 85, "project_engineer", "critical_skills", "high", "candidate")

    monkeypatch.setattr(client, "_groq_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("groq")))
    monkeypatch.setattr(client, "_gemini_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("gemini")))

    result = client.refine(vacancy, preliminary)
    assert result.provisional
    assert result is preliminary


def test_ai_canonicalizes_known_permit_aliases():
    data = valid()
    data["permit_path"] = "critical_skills_plausible"
    assert AIClient._validate(data).permit_path == "critical_skills"


def test_two_provider_disagreement_does_not_promote_weak_deterministic_candidate():
    preliminary = Assessment(False, 72, "infrastructure_engineer", "unclear", "medium", "ambiguous")
    first = Assessment(False, 70, "infrastructure_engineer", "unclear", "medium", "no", source="ai-groq")
    second = Assessment(True, 90, "infrastructure_engineer", "critical_skills", "high", "yes", source="ai-gemini")
    result = AIClient._consolidate(preliminary, [first, second], 76)
    assert not result.matched
    assert result.source == "ai-consensus"


def test_two_provider_disagreement_can_preserve_strong_deterministic_civil_candidate():
    preliminary = Assessment(True, 86, "project_engineer", "critical_skills", "high", "civil")
    first = Assessment(False, 74, "project_engineer", "unclear", "medium", "no", source="ai-groq")
    second = Assessment(True, 90, "project_engineer", "critical_skills", "high", "yes", source="ai-gemini")
    result = AIClient._consolidate(preliminary, [first, second], 76)
    assert result.matched
