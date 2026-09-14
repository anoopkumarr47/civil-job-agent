from civil_job_agent.sources.jobsireland import JobRef, JobsIrelandSource


def _source():
    return JobsIrelandSource(
        {
            "name": "JobsIreland",
            "search_terms": ["civil engineer", "site engineer"],
            "page_size": 100,
            "max_pages": 1,
            "max_links": 120,
            "navigation_timeout_ms": 25000,
            "search_budget_seconds": 180,
            "detail_budget_seconds": 180,
            "settle_ms": 1000,
        },
        max_links=120,
    )


def test_search_url_contains_keyword_and_page_size():
    source = _source()
    url = source._search_url("civil engineer", 1)
    assert "keyWord=civil+engineer" in url
    assert "pageSize=100" in url
    assert "page=1" in url


def test_job_id_extraction_accepts_only_numeric_detail_ids():
    assert (
        JobsIrelandSource._job_id_from_url(
            "https://jobsireland.ie/en-US/job-Details?id=2455502"
        )
        == "2455502"
    )
    assert JobsIrelandSource._job_id_from_url(
        "https://jobsireland.ie/en-US/job-Details?id="
    ) is None
    assert JobsIrelandSource._job_id_from_url(
        "https://jobsireland.ie/en-US/job-Details?id=abc"
    ) is None
    assert JobsIrelandSource._job_id_from_url(
        "https://jobsireland.ie/en-US/browse-jobs?keyWord=civil"
    ) is None


def test_anchor_extraction_deduplicates_vacancy_ids():
    anchors = [
        {
            "href": "https://jobsireland.ie/en-US/job-Details?id=2455502",
            "text": "Civil Engineer",
        },
        {
            "href": "https://jobsireland.ie/en-US/job-Details?id=2455502",
            "text": "Civil Engineer duplicate",
        },
        {
            "href": "https://jobsireland.ie/en-US/job-Details?id=2455497",
            "text": "Site Engineer",
        },
    ]
    refs = JobsIrelandSource._refs_from_anchors(anchors)
    assert [ref.job_id for ref in refs] == ["2455502", "2455497"]


def test_job_ref_generates_canonical_detail_url():
    ref = JobRef("2455502", "Civil Engineer")
    assert ref.url == "https://jobsireland.ie/en-US/job-Details?id=2455502"


def test_detail_parser_uses_jsonld_when_available():
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Civil Engineer",
        "hiringOrganization": {"@type": "Organization", "name": "Example Civil"},
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Dublin",
            "addressCountry": "Ireland"
          }
        },
        "description": "<p>Design roads and civil infrastructure using Civil 3D. Minimum five years experience in highway engineering and site supervision.</p>",
        "datePosted": "2026-09-13",
        "baseSalary": {
          "@type": "MonetaryAmount",
          "currency": "EUR",
          "value": {
            "@type": "QuantitativeValue",
            "minValue": 50000,
            "maxValue": 60000,
            "unitText": "YEAR"
          }
        }
      }
      </script>
    </head><body></body></html>
    """
    job = JobsIrelandSource._parse_detail_html(
        html,
        JobRef("2455502", "Civil Engineer"),
    )
    assert job is not None
    assert job.source == "JobsIreland"
    assert job.title == "Civil Engineer"
    assert job.company == "Example Civil"
    assert "Dublin" in job.location
    assert "Civil 3D" in job.text
    assert "50000" in job.salary_text
    assert job.url.endswith("id=2455502")


def test_detail_parser_falls_back_to_rendered_text():
    html = """
    <html><body>
      <h1>Resident Engineer</h1>
      <div class="company">Example Consultancy</div>
      <main>
        Resident Engineer position in Cork, Ireland.
        Civil roads infrastructure role with contractor supervision,
        site inspection and six years of engineering experience.
        Salary: €58,000 per annum.
      </main>
    </body></html>
    """
    job = JobsIrelandSource._parse_detail_html(
        html,
        JobRef("2455000", "Resident Engineer"),
    )
    assert job is not None
    assert job.title == "Resident Engineer"
    assert "Cork" in job.location
    assert job.company == "Example Consultancy"
    assert "€58,000" in job.salary_text
