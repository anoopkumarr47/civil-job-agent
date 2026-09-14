import pytest

from civil_job_agent.ai import AIClient, compact_job_evidence
from civil_job_agent.models import Assessment, Job


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
    assert AIClient._schema_generation_error(
        '{"code":"json_validate_failed","message":"Failed to validate JSON"}'
    )
    assert not AIClient._schema_generation_error("invalid API key")


def test_compact_evidence_limits_size_and_keeps_requirements():
    text = (
        "Introduction text. " * 80
        + "Minimum 5 years experience in civil roads. "
        + "Civil 3D and AutoCAD are required. "
        + "No visa sponsorship is available. "
        + "Salary €55,000 per annum. "
        + ("Generic company text. " * 150)
    )
    vacancy = Job("test", "https://example/1", "Civil Engineer", "Firm", "Dublin", text)
    evidence = compact_job_evidence(vacancy, 1400)
    assert len(evidence) <= 1400
    assert "Minimum 5 years experience" in evidence
    assert "No visa sponsorship" in evidence


def test_cerebras_reasoning_is_high_for_borderline_role():
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 80, "project_engineer", "critical_skills_plausible", "high", "fit")
    assert AIClient._reasoning_effort(vacancy, preliminary, 76) == "high"


def test_cerebras_reasoning_is_medium_for_clear_role():
    vacancy = Job("test", "https://example/1", "Highway Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 96, "highway_engineer", "critical_skills_plausible", "high", "fit")
    assert AIClient._reasoning_effort(vacancy, preliminary, 76) == "medium"


def test_clear_cerebras_result_does_not_need_second_opinion():
    vacancy = Job("test", "https://example/1", "Highway Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 96, "highway_engineer", "critical_skills_plausible", "high", "fit")
    primary = Assessment(True, 94, "highway_engineer", "critical_skills", "high", "fit", source="ai-cerebras")
    assert not AIClient._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_borderline_cerebras_result_needs_second_opinion():
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 84, "project_engineer", "critical_skills_plausible", "high", "fit")
    primary = Assessment(True, 78, "project_engineer", "critical_skills", "high", "fit", source="ai-cerebras")
    assert AIClient._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_refine_uses_cerebras_primary_and_groq_second_opinion(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(
        replace(
            settings,
            cerebras_api_key="cerebras-key",
            ai_api_key="groq-key",
        )
    )
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 84, "project_engineer", "critical_skills_plausible", "high", "fit")
    calls = []

    def fake_cerebras(job, preliminary, threshold):
        calls.append("cerebras")
        return Assessment(True, 78, "project_engineer", "critical_skills", "high", "c", source="ai-cerebras")

    def fake_groq(job, preliminary, reasoning_effort="medium"):
        calls.append(("groq", reasoning_effort))
        return Assessment(True, 88, "project_engineer", "critical_skills", "high", "g", source="ai-groq")

    monkeypatch.setattr(client, "_cerebras_call", fake_cerebras)
    monkeypatch.setattr(client, "_groq_call", fake_groq)

    result = client.refine(vacancy, preliminary, threshold=76)
    assert calls == ["cerebras", ("groq", "high")]
    assert result.source == "ai-consensus"
    assert result.matched


def test_groq_falls_back_when_cerebras_fails(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(
        replace(
            settings,
            cerebras_api_key="cerebras-key",
            ai_api_key="groq-key",
        )
    )
    vacancy = Job("test", "https://example/1", "Civil Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 90, "civil_engineer", "critical_skills_plausible", "high", "fit")

    monkeypatch.setattr(client, "_cerebras_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(
        client,
        "_groq_call",
        lambda *args, **kwargs: Assessment(
            True, 91, "civil_engineer", "critical_skills", "high", "groq", source="ai-groq"
        ),
    )
    result = client.refine(vacancy, preliminary)
    assert result.source == "ai-groq"
    assert result.score == 91


def test_all_provider_failures_become_provisional_in_production(settings, monkeypatch):
    from dataclasses import replace

    client = AIClient(
        replace(
            settings,
            cerebras_api_key="cerebras-key",
            ai_api_key="groq-key",
            gemini_api_key=None,
            ai_required=False,
        )
    )
    vacancy = Job("test", "https://example/1", "Project Engineer", "Firm", "Dublin", "civil roads")
    preliminary = Assessment(True, 85, "project_engineer", "critical_skills", "high", "candidate")

    monkeypatch.setattr(client, "_cerebras_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("cerebras")))
    monkeypatch.setattr(client, "_groq_call", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("groq")))

    result = client.refine(vacancy, preliminary)
    assert result.provisional
    assert result is preliminary


def test_ai_canonicalizes_known_permit_aliases():
    data = valid()
    data["permit_path"] = "critical_skills_plausible"
    assert AIClient._validate(data).permit_path == "critical_skills"

    data = valid()
    data["permit_path"] = "general_employment_permit"
    assert AIClient._validate(data).permit_path == "general"


def test_consensus_preserves_strong_plausible_candidate_on_two_provider_disagreement():
    preliminary = Assessment(True, 82, "project_engineer", "critical_skills_plausible", "high", "fit")
    first = Assessment(False, 73, "project_engineer", "unclear", "medium", "no", source="ai-cerebras")
    second = Assessment(True, 86, "project_engineer", "critical_skills", "high", "yes", source="ai-groq")
    result = AIClient._consolidate(preliminary, [first, second], 76)
    assert result.matched
    assert result.source == "ai-consensus"
    assert any("disagreed" in gap.lower() for gap in result.gaps)


def test_three_provider_consensus_uses_majority():
    preliminary = Assessment(True, 82, "project_engineer", "critical_skills_plausible", "high", "fit")
    assessments = [
        Assessment(True, 88, "project_engineer", "critical_skills", "high", "c", source="ai-cerebras"),
        Assessment(False, 72, "project_engineer", "unclear", "medium", "g", source="ai-groq"),
        Assessment(True, 84, "project_engineer", "critical_skills", "high", "m", source="ai-gemini"),
    ]
    result = AIClient._consolidate(preliminary, assessments, 76)
    assert result.matched
    assert result.score == 84
    assert result.permit_path == "critical_skills"
