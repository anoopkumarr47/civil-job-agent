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


def vacancy(title="Project Engineer"):
    return Job("test", "https://example/1", title, "Firm", "Dublin", "civil roads")


def preliminary():
    return Assessment(True, 84, "project_engineer", "critical_skills", "high", "fit")


def http_error(status: int, text: str = "bad request", retry_after: str | None = None):
    response = requests.Response()
    response.status_code = status
    response._content = text.encode()
    response.url = "https://example.invalid"
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return requests.HTTPError(f"{status} error", response=response)


def test_validate_is_strict():
    data = valid()
    data["matched"] = "yes"
    with pytest.raises(ValueError, match="JSON boolean"):
        AIClient._validate(data)
    data = valid()
    data["role_family"] = None
    with pytest.raises(ValueError, match="role_family"):
        AIClient._validate(data)


def test_compact_evidence_keeps_domain_and_blocker_signals():
    job = Job(
        "test",
        "https://example/1",
        "Infrastructure Engineer",
        "Firm",
        "Dublin",
        "Intro. " * 100
        + "Civil roads Civil 3D. AWS Terraform cloud. No visa sponsorship. Salary €55,000.",
    )
    evidence = compact_job_evidence(job, 1800)
    assert "Civil roads" in evidence
    assert "AWS" in evidence
    assert "sponsorship" in evidence


def test_provider_states_are_model_and_vendor_specific(settings):
    client = AIClient(
        replace(
            settings,
            groq_api_key="g",
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            gemini_api_key="m",
        )
    )
    assert client.providers["groq_primary"].model == "openai/gpt-oss-20b"
    assert client.providers["groq_primary"].vendor == "groq"
    assert client.providers["cloudflare"].model == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert client.providers["cloudflare"].vendor == "cloudflare"
    assert client.providers["groq_backup"].model == "openai/gpt-oss-120b"
    assert client.providers["gemini"].vendor == "gemini"


def test_generic_400_does_not_disable_lane_immediately(settings):
    client = AIClient(replace(settings, groq_api_key="g"))
    client._handle_provider_error("groq_primary", http_error(400, "request-specific"))
    state = client.providers["groq_primary"]
    assert not state.disabled_reason
    assert state.failures == 1


def test_preflight_incompatibility_disables_only_lane(settings):
    client = AIClient(replace(settings, groq_api_key="g"))
    client._handle_provider_error(
        "groq_primary",
        http_error(400, "unsupported request"),
        preflight=True,
    )
    assert client.providers["groq_primary"].disabled_reason
    assert client.providers["groq_backup"].operational()


def test_429_is_per_model_cooldown(settings):
    client = AIClient(replace(settings, groq_api_key="g"))
    client._handle_provider_error(
        "groq_primary",
        http_error(429, "TPM", retry_after="2"),
    )
    assert not client.providers["groq_primary"].ready()
    assert client.providers["groq_backup"].ready()
    assert not client.providers["groq_primary"].disabled_reason


def test_daily_quota_disables_gemini_for_run(settings):
    client = AIClient(replace(settings, gemini_api_key="m"))
    client._handle_provider_error(
        "gemini",
        http_error(429, "GenerateRequestsPerDayPerProjectPerModel-FreeTier"),
    )
    assert client.providers["gemini"].disabled_reason == "daily quota exhausted"


def test_auth_failure_disables_only_affected_lane(settings):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))
    client._handle_provider_error("groq_primary", http_error(401, "bad key"))
    assert not client.providers["groq_primary"].operational()
    assert client.providers["groq_backup"].operational()
    assert client.providers["gemini"].operational()


def test_waterfall_uses_backup_groq_before_gemini(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))
    calls = []

    def fake_call(provider, job, prelim, preflight=False):
        calls.append(provider)
        if provider == "groq_primary":
            raise http_error(429, "TPM", retry_after="60")
        if provider == "groq_backup":
            return Assessment(
                True, 86, "project_engineer", "critical_skills", "high", "fit",
                source="ai-groq_backup",
            )
        raise AssertionError("Gemini should not be used")

    monkeypatch.setattr(client, "_call_provider", fake_call)
    result = client.refine(vacancy(), preliminary())
    assert calls == ["groq_primary", "groq_backup"]
    assert result.source == "ai-groq_backup"


def test_waterfall_reaches_gemini_only_after_both_groq_lanes_fail(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))
    calls = []

    def fake_call(provider, job, prelim, preflight=False):
        calls.append(provider)
        if provider.startswith("groq_"):
            raise http_error(503, "temporary")
        return Assessment(
            True, 87, "project_engineer", "critical_skills", "high", "fit",
            source="ai-gemini",
        )

    monkeypatch.setattr(client, "_call_provider", fake_call)
    result = client.refine(vacancy(), preliminary())
    assert calls == ["groq_primary", "groq_backup", "gemini"]
    assert result.source == "ai-gemini"


def test_one_valid_decision_does_not_trigger_second_opinion(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))
    calls = []

    def fake_call(provider, job, prelim, preflight=False):
        calls.append(provider)
        return Assessment(
            True, 82, "project_engineer", "critical_skills", "high", "fit",
            source=f"ai-{provider}",
        )

    monkeypatch.setattr(client, "_call_provider", fake_call)
    result = client.refine(vacancy(), preliminary())
    assert calls == ["groq_primary"]
    assert result.source == "ai-groq_primary"


def test_all_lanes_failed_becomes_provisional(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))

    monkeypatch.setattr(
        client,
        "_call_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(client, "_wait_for_recovery", lambda *args, **kwargs: False)

    before = preliminary()
    result = client.refine(vacancy(), before)
    assert result is before
    assert result.provisional


def test_preflight_checks_all_configured_lanes(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g", gemini_api_key="m"))
    calls = []

    def fake_call(provider, job, prelim, preflight=False):
        calls.append((provider, preflight))
        return Assessment(
            True, 95, "highway_engineer", "critical_skills", "high", "ok",
            source=f"ai-{provider}",
        )

    monkeypatch.setattr(client, "_call_provider", fake_call)
    health = client.preflight()
    assert calls == [
        ("groq_primary", True),
        ("groq_backup", True),
        ("gemini", True),
    ]
    assert all(
        state["operational"]
        for state in health.values()
        if state["configured"]
    )


def test_groq_strict_fallback_is_not_sticky(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g"))
    modes = []

    def fake_request(provider, job, prelim, *, mode="strict", reasoning_effort="low", preflight=False):
        modes.append(mode)
        if len(modes) == 1:
            raise ValueError("bad strict payload")
        return Assessment(
            True, 90, "civil_engineer", "critical_skills", "high", "fit",
            source=f"ai-{provider}",
        )

    monkeypatch.setattr(client, "_groq_request", fake_request)
    result = client._groq_call("groq_primary", vacancy("Civil Engineer"), preliminary())
    assert modes == ["strict", "json_object"]
    assert client.providers["groq_primary"].mode == "strict"
    assert result.matched


def test_groq_request_uses_selected_model_and_current_parameters(settings, monkeypatch):
    client = AIClient(replace(settings, groq_api_key="g"))
    captured = {}

    class FakeResponse:
        headers = {}
        def json(self):
            return {"choices": [{"message": {"content": __import__("json").dumps(valid())}}]}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr(client.http, "request", fake_request)
    result = client._groq_request(
        "groq_backup",
        vacancy("Civil Engineer"),
        Assessment(True, 90, "civil_engineer", "critical_skills", "high", "fit"),
    )
    assert result.matched
    assert captured["model"] == "openai/gpt-oss-120b"
    assert captured["max_completion_tokens"] == 320
    assert captured["response_format"]["type"] == "json_schema"


def test_gemini_uses_flash_lite_minimal_thinking_and_json_schema(settings, monkeypatch):
    client = AIClient(replace(settings, gemini_api_key="m"))
    captured = {}

    class FakeResponse:
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": __import__("json").dumps(valid())}]}}]
            }

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr(client.http, "request", fake_request)
    result = client._gemini_request(
        vacancy("Civil Engineer"),
        Assessment(True, 90, "civil_engineer", "critical_skills", "high", "fit"),
    )
    generation = captured["payload"]["generationConfig"]
    assert "gemini-3.1-flash-lite" in captured["url"]
    assert generation["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert "responseJsonSchema" in generation
    assert result.matched


def test_groq_rate_headers_cool_only_current_model(settings):
    client = AIClient(replace(settings, groq_api_key="g"))

    class FakeResponse:
        headers = {
            "x-ratelimit-remaining-tokens": "1400",
            "x-ratelimit-reset-tokens": "1.5s",
        }

    client._apply_groq_rate_headers("groq_primary", FakeResponse())
    assert not client.providers["groq_primary"].ready()
    assert client.providers["groq_backup"].ready()


def test_cloudflare_request_uses_openai_compatible_schema(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            cloudflare_account_id="acct",
            cloudflare_api_token="cf-token",
        )
    )
    captured = {}

    class FakeResponse:
        def json(self):
            return {
                "choices": [
                    {"message": {"content": __import__("json").dumps(valid())}}
                ]
            }

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs["json"]
        captured["headers"] = kwargs["headers"]
        return FakeResponse()

    monkeypatch.setattr(client.http, "request", fake_request)
    result = client._cloudflare_request(vacancy(), preliminary())

    assert "/accounts/acct/ai/v1/chat/completions" in captured["url"]
    assert captured["payload"]["model"] == "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
    assert captured["payload"]["response_format"]["type"] == "json_schema"
    assert captured["payload"]["response_format"]["json_schema"] == __import__("civil_job_agent.ai", fromlist=["SCHEMA"]).SCHEMA
    assert captured["headers"]["Authorization"] == "Bearer cf-token"
    assert result.source == "ai-cloudflare"


def test_cloudflare_budget_stops_new_requests(settings):
    client = AIClient(
        replace(
            settings,
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            cloudflare_run_call_budget=2,
        )
    )
    client.providers["cloudflare"].requests_made = 2
    assert not client._cloudflare_budget_available()
    assert "cloudflare" not in client._routing_order()


def test_cloudflare_daily_neuron_exhaustion_disables_lane(settings):
    client = AIClient(
        replace(
            settings,
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
        )
    )
    client._handle_provider_error(
        "cloudflare",
        http_error(429, "3036 You have used up your daily free allocation of 10,000 Neurons"),
    )
    assert client.providers["cloudflare"].disabled_reason == "daily quota exhausted"


def test_cloudflare_out_of_capacity_is_temporary(settings):
    client = AIClient(
        replace(
            settings,
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
        )
    )
    client._handle_provider_error(
        "cloudflare",
        http_error(429, "3040 Out of capacity"),
    )
    assert not client.providers["cloudflare"].disabled_reason
    assert not client.providers["cloudflare"].ready()


def test_workhorses_balance_between_groq_and_cloudflare(settings):
    client = AIClient(
        replace(
            settings,
            groq_api_key="g",
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            gemini_api_key="m",
        )
    )
    first = client._routing_order()
    assert first[:2] == ["groq_primary", "cloudflare"]

    client.providers["groq_primary"].successes = 2
    client.providers["cloudflare"].successes = 1
    second = client._routing_order()
    assert second[0] == "cloudflare"


def test_preflight_checks_cloudflare_too(settings, monkeypatch):
    client = AIClient(
        replace(
            settings,
            groq_api_key="g",
            cloudflare_account_id="acct",
            cloudflare_api_token="cf",
            gemini_api_key="m",
        )
    )
    calls = []

    def fake_call(provider, job, prelim, preflight=False):
        calls.append((provider, preflight))
        return Assessment(
            True, 95, "highway_engineer", "critical_skills", "high", "ok",
            source=f"ai-{provider}",
        )

    monkeypatch.setattr(client, "_call_provider", fake_call)
    client.preflight()
    assert calls == [
        ("groq_primary", True),
        ("cloudflare", True),
        ("groq_backup", True),
        ("gemini", True),
    ]
