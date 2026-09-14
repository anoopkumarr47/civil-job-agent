from dataclasses import replace

import pytest
import requests

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


def http_error(status: int, text: str = "bad request", retry_after: str | None = None):
    response = requests.Response()
    response.status_code = status
    response._content = text.encode()
    response.url = "https://example.invalid"
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return requests.HTTPError(f"{status} error", response=response)


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
    assert AIClient._schema_generation_error("response_format json_schema invalid")
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
    vacancy = Job(
        "test",
        "https://example/1",
        "Infrastructure Engineer",
        "Firm",
        "Dublin",
        text,
    )
    evidence = compact_job_evidence(vacancy, 1800)
    assert len(evidence) <= 1800
    assert "civil roads" in evidence
    assert "AWS" in evidence


def test_generic_400_does_not_immediately_disable_provider(settings):
    client = AIClient(replace(settings, groq_api_key="groq-key"))
    client._handle_provider_error("groq", http_error(400, "request-specific error"))
    assert client.providers["groq"].disabled_reason == ""
    assert client.providers["groq"].failures == 1


def test_preflight_400_disables_incompatible_provider(settings):
    client = AIClient(replace(settings, groq_api_key="groq-key"))
    client._handle_provider_error(
        "groq",
        http_error(400, "unsupported request"),
        preflight=True,
    )
    assert "preflight incompatible" in client.providers["groq"].disabled_reason


def test_rate_limit_uses_cooldown_not_permanent_disable(settings):
    client = AIClient(replace(settings, groq_api_key="groq-key"))
    client._handle_provider_error(
        "groq",
        http_error(429, "rate limit", retry_after="12"),
    )
    state = client.providers["groq"]
    assert state.disabled_reason == ""
    assert state.cooldown_until > 0
    assert not state.ready()


def test_auth_error_disables_provider(settings):
    client = AIClient(replace(settings, gemini_api_key="gemini-key"))
    client._handle_provider_error("gemini", http_error(401, "invalid key"))
    assert client.providers["gemini"].disabled_reason


def test_clear_highway_result_does_not_need_second_opinion(settings):
    client = AIClient(settings)
    vacancy = Job(
        "test",
        "https://example/1",
        "Highway Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    preliminary = Assessment(
        True, 96, "highway_engineer", "critical_skills", "high", "fit"
    )
    primary = Assessment(
        True,
        94,
        "highway_engineer",
        "critical_skills",
        "high",
        "fit",
        source="ai-groq",
    )
    assert not client._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_ambiguous_infrastructure_result_needs_second_opinion(settings):
    client = AIClient(settings)
    vacancy = Job(
        "test",
        "https://example/1",
        "Infrastructure Engineer",
        "Firm",
        "Dublin",
        "civil works",
    )
    preliminary = Assessment(
        False, 72, "infrastructure_engineer", "unclear", "medium", "review"
    )
    primary = Assessment(
        True,
        82,
        "infrastructure_engineer",
        "critical_skills",
        "high",
        "fit",
        source="ai-groq",
    )
    assert client._needs_second_opinion(vacancy, preliminary, primary, 76)


def test_refine_fails_over_to_gemini_immediately(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
        )
    )
    vacancy = Job(
        "test",
        "https://example/1",
        "Project Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    preliminary = Assessment(
        True, 84, "project_engineer", "critical_skills", "high", "fit"
    )
    calls = []

    def fail_groq(*args, **kwargs):
        calls.append("groq")
        raise http_error(429, "quota", retry_after="60")

    def good_gemini(*args, **kwargs):
        calls.append("gemini")
        return Assessment(
            True,
            88,
            "project_engineer",
            "critical_skills",
            "high",
            "fit",
            source="ai-gemini",
        )

    monkeypatch.setattr(client, "_groq_call", fail_groq)
    monkeypatch.setattr(client, "_gemini_call", good_gemini)

    result = client.refine(vacancy, preliminary)
    assert calls == ["groq", "gemini"]
    assert result.source == "ai-gemini"
    assert client.providers["groq"].disabled_reason == ""


def test_refine_uses_independent_second_opinion(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
        )
    )
    vacancy = Job(
        "test",
        "https://example/1",
        "Project Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    preliminary = Assessment(
        True, 84, "project_engineer", "critical_skills", "high", "fit"
    )
    calls = []

    def fake_groq(job, preliminary, reasoning_effort="low", preflight=False):
        calls.append(("groq", reasoning_effort))
        return Assessment(
            True,
            78,
            "project_engineer",
            "critical_skills",
            "high",
            "g",
            source="ai-groq",
        )

    def fake_gemini(job, preliminary, preflight=False):
        calls.append("gemini")
        return Assessment(
            True,
            88,
            "project_engineer",
            "critical_skills",
            "high",
            "m",
            source="ai-gemini",
        )

    monkeypatch.setattr(client, "_groq_call", fake_groq)
    monkeypatch.setattr(client, "_gemini_call", fake_gemini)

    result = client.refine(vacancy, preliminary, threshold=76)
    assert calls == [("groq", "low"), "gemini"]
    assert result.source == "ai-consensus"
    assert result.matched


def test_all_provider_failures_become_provisional(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
            ai_required=False,
        )
    )
    vacancy = Job(
        "test",
        "https://example/1",
        "Project Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    preliminary = Assessment(
        True, 85, "project_engineer", "critical_skills", "high", "candidate"
    )

    monkeypatch.setattr(
        client,
        "_groq_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("groq")),
    )
    monkeypatch.setattr(
        client,
        "_gemini_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("gemini")),
    )

    result = client.refine(vacancy, preliminary)
    assert result.provisional
    assert result is preliminary


def test_preflight_can_leave_one_provider_healthy(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            groq_api_key="groq-key",
            gemini_api_key="gemini-key",
        )
    )

    monkeypatch.setattr(
        client,
        "_groq_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            http_error(401, "bad groq key")
        ),
    )
    monkeypatch.setattr(
        client,
        "_gemini_call",
        lambda *args, **kwargs: Assessment(
            True,
            95,
            "highway_engineer",
            "critical_skills",
            "high",
            "ok",
            source="ai-gemini",
        ),
    )

    health = client.preflight()
    assert not health["groq"]["ready"]
    assert health["gemini"]["ready"]
    assert client.available


def test_groq_request_uses_current_reasoning_parameters(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="groq-key"))
    captured = {}

    class FakeResponse:
        def json(self):
            return {"choices": [{"message": {"content": __import__("json").dumps(valid())}}]}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr(client.http, "request", fake_request)
    vacancy = Job(
        "test",
        "https://example/1",
        "Civil Engineer",
        "Firm",
        "Dublin",
        "civil roads",
    )
    preliminary = Assessment(
        True, 90, "civil_engineer", "critical_skills", "high", "fit"
    )

    client._groq_request(
        vacancy,
        preliminary,
        reasoning_effort="low",
        mode="strict",
    )
    assert captured["model"] == "openai/gpt-oss-20b"
    assert captured["max_completion_tokens"] == 500
    assert captured["include_reasoning"] is False
    assert "max_tokens" not in captured
    assert "reasoning_format" not in captured


def test_ai_canonicalizes_known_permit_aliases():
    data = valid()
    data["permit_path"] = "critical_skills_plausible"
    assert AIClient._validate(data).permit_path == "critical_skills"


def test_two_provider_disagreement_does_not_promote_weak_deterministic_candidate():
    preliminary = Assessment(
        False, 72, "infrastructure_engineer", "unclear", "medium", "ambiguous"
    )
    first = Assessment(
        False,
        70,
        "infrastructure_engineer",
        "unclear",
        "medium",
        "no",
        source="ai-groq",
    )
    second = Assessment(
        True,
        90,
        "infrastructure_engineer",
        "critical_skills",
        "high",
        "yes",
        source="ai-gemini",
    )
    result = AIClient._consolidate(preliminary, [first, second], 76)
    assert not result.matched
    assert result.source == "ai-consensus"


def test_two_provider_disagreement_can_preserve_strong_deterministic_civil_candidate():
    preliminary = Assessment(
        True, 86, "project_engineer", "critical_skills", "high", "civil"
    )
    first = Assessment(
        False,
        74,
        "project_engineer",
        "unclear",
        "medium",
        "no",
        source="ai-groq",
    )
    second = Assessment(
        True,
        90,
        "project_engineer",
        "critical_skills",
        "high",
        "yes",
        source="ai-gemini",
    )
    result = AIClient._consolidate(preliminary, [first, second], 76)
    assert result.matched
