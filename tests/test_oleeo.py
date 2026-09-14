from civil_job_agent.sources.oleeo import OleeoSource


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _source():
    return OleeoSource(
        {
            "name": "PublicJobs",
            "landing_url": "https://publicjobs.example/",
            "board_host": "publicjobs.tal.net",
            "allowed_hosts": ["publicjobs.tal.net"],
            "job_link_patterns": ["/candidate/so/", "/opp/"],
            "max_pages": 3,
            "max_links": 20,
            "assume_ireland": True,
        },
        request_timeout=5,
        max_links=20,
    )


def test_oleeo_discovers_board_and_follows_next_page(monkeypatch):
    source = _source()
    landing = '<a href="https://publicjobs.tal.net/board/page1">Job Search</a>'
    page1 = """
      <a href="/candidate/so/pm/1/pl/3/opp/1-Senior-Executive-Engineer/en-GB">Senior Executive Engineer</a>
      <a href="/candidate/so/pm/1/pl/3/opp/2-ICT-Infrastructure-Manager/en-GB">ICT Infrastructure Manager</a>
      <a href="/board/page2">Next page</a>
    """
    page2 = """
      <a href="/candidate/so/pm/1/pl/3/opp/3-Executive-Engineer/en-GB">Executive Engineer</a>
    """

    def fake_request(method, url, **kwargs):
        if url == "https://publicjobs.example/":
            return FakeResponse(landing)
        if "page2" in url:
            return FakeResponse(page2)
        return FakeResponse(page1)

    monkeypatch.setattr(source.client, "request", fake_request)
    links = source._discover_links()
    assert len(links) == 2
    assert any("Senior-Executive-Engineer" in link for link in links)
    assert any("Executive-Engineer" in link for link in links)
