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
