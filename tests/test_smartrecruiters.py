from civil_job_agent.sources.smartrecruiters import SmartRecruitersCompanySource


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_smartrecruiters_discovers_irish_civil_role(monkeypatch):
    source = SmartRecruitersCompanySource(
        {
            "name": "AECOM",
            "company_identifier": "AECOM2",
            "country": "ie",
            "max_links": 20,
        },
        request_timeout=5,
        max_links=20,
    )

    listing = {
        "limit": 100,
        "offset": 0,
        "totalFound": 1,
        "content": [
            {
                "id": "123",
                "name": "Civil Engineer",
                "releasedDate": "2026-09-01T00:00:00Z",
                "location": {"city": "Dublin", "country": "ie"},
                "company": {"name": "AECOM"},
                "ref": "https://api.smartrecruiters.com/v1/companies/AECOM2/postings/123",
            }
        ],
    }
    detail = {
        "id": "123",
        "name": "Civil Engineer",
        "location": {"city": "Dublin", "country": "ie"},
        "company": {"name": "AECOM"},
        "jobAd": {
            "jobDescription": "<p>Design roads and civil infrastructure using Civil 3D.</p>",
            "qualifications": "<p>Five years civil engineering experience.</p>",
        },
        "applyUrl": "https://jobs.smartrecruiters.com/AECOM2/123",
    }

    def fake_request(method, url, **kwargs):
        return FakeResponse(detail if url.endswith("/123") else listing)

    monkeypatch.setattr(source.client, "request", fake_request)
    jobs = source.discover()

    assert len(jobs) == 1
    assert jobs[0].title == "Civil Engineer"
    assert jobs[0].company == "AECOM"
    assert "Civil 3D" in jobs[0].text
    assert jobs[0].location.startswith("Dublin")


def test_smartrecruiters_skips_non_target_title(monkeypatch):
    source = SmartRecruitersCompanySource(
        {"name": "AECOM", "company_identifier": "AECOM2", "country": "ie"},
        request_timeout=5,
        max_links=20,
    )
    listing = {
        "limit": 100,
        "offset": 0,
        "totalFound": 1,
        "content": [
            {
                "id": "999",
                "name": "Finance Manager",
                "location": {"city": "Dublin", "country": "ie"},
            }
        ],
    }

    monkeypatch.setattr(source.client, "request", lambda *args, **kwargs: FakeResponse(listing))
    assert source.discover() == []


def test_irrelevant_postings_do_not_consume_candidate_cap(monkeypatch):
    source = SmartRecruitersCompanySource(
        {
            "name": "AECOM",
            "company_identifier": "AECOM2",
            "country": "ie",
            "max_links": 1,
        },
        request_timeout=5,
        max_links=1,
    )
    first_page = {
        "limit": 2,
        "offset": 0,
        "totalFound": 3,
        "content": [
            {"id": "1", "name": "Finance Manager", "location": {"city": "Dublin", "country": "ie"}},
            {"id": "2", "name": "HR Business Partner", "location": {"city": "Dublin", "country": "ie"}},
        ],
    }
    second_page = {
        "limit": 2,
        "offset": 2,
        "totalFound": 3,
        "content": [
            {
                "id": "3",
                "name": "Civil Engineer",
                "location": {"city": "Dublin", "country": "ie"},
                "ref": "https://api.smartrecruiters.com/v1/companies/AECOM2/postings/3",
            }
        ],
    }
    detail = {
        "id": "3",
        "name": "Civil Engineer",
        "location": {"city": "Dublin", "country": "ie"},
        "company": {"name": "AECOM"},
        "jobAd": {
            "jobDescription": "<p>Civil engineering roads drainage and transport infrastructure.</p>",
            "qualifications": "<p>Five years experience.</p>",
        },
        "applyUrl": "https://jobs.smartrecruiters.com/AECOM2/3",
    }

    def fake_request(method, url, **kwargs):
        if url.endswith("/3"):
            return FakeResponse(detail)
        if "offset=2" in url:
            return FakeResponse(second_page)
        return FakeResponse(first_page)

    monkeypatch.setattr(source.client, "request", fake_request)
    jobs = source.discover()
    assert [job.title for job in jobs] == ["Civil Engineer"]
