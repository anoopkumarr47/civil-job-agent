from civil_job_agent.models import Job, canonicalize_url


def test_tracking_parameters_are_removed():
    assert canonicalize_url("https://Example.com/job/1/?utm_source=x&foo=bar#x") == "https://example.com/job/1?foo=bar"


def test_same_title_company_location_dedupes_by_identity():
    a = Job("A", "https://a/1", "Civil Engineer", "Firm", "Dublin", "x")
    b = Job("B", "https://b/2", "Civil Engineer", "Firm", "Dublin", "longer")
    assert a.identity_key == b.identity_key
