from civil_job_agent.models import Job, canonicalize_url


def test_tracking_parameters_are_removed():
    assert canonicalize_url("https://Example.com/job/1/?utm_source=x&foo=bar#x") == "https://example.com/job/1?foo=bar"


def test_distinct_requisitions_keep_distinct_identity():
    a = Job("A", "https://a/1", "Civil Engineer", "Firm", "Dublin", "same")
    b = Job("B", "https://b/2", "Civil Engineer", "Firm", "Dublin", "same")
    assert a.identity_key != b.identity_key
    assert a.duplicate_signature == b.duplicate_signature


def test_same_canonical_url_has_same_identity():
    a = Job("A", "https://example.com/jobs/1?utm_source=x", "Civil Engineer", "Firm", "Dublin", "x")
    b = Job("B", "https://example.com/jobs/1", "Civil Engineer", "Firm", "Dublin", "y")
    assert a.identity_key == b.identity_key


def test_posted_age_does_not_change_content_hash():
    a = Job("A", "https://a/1", "Civil Engineer", "Firm", "Dublin", "same description", "€50,000", "1 day ago")
    b = Job("A", "https://a/1", "Civil Engineer", "Firm", "Dublin", "same description", "€50,000", "2 days ago")
    assert a.content_hash == b.content_hash
