from civil_job_agent.sources.successfactors import SuccessFactorsSource


class FakeResponse:
    def __init__(self, text):
        self.text = text


def _source():
    return SuccessFactorsSource(
        {
            "name": "Mott MacDonald",
            "search_url": "https://apply.example/search/?q=",
            "allowed_hosts": ["apply.example"],
            "job_link_patterns": ["/job/"],
            "required_any_terms": ["civil", "roads", "engineer"],
            "page_size": 20,
            "max_pages": 3,
            "max_links": 20,
        },
        request_timeout=5,
        max_links=20,
    )


def test_successfactors_discovers_irish_plausible_titles_across_pages(monkeypatch):
    source = _source()
    pages = {
        0: """
        <table>
          <tr><td><a href="/job/London-Software-Engineer/1/">Software Engineer</a></td><td>London, GB</td></tr>
          <tr><td><a href="/job/London-Civil-Engineer/2/">Civil Engineer</a></td><td>London, GB</td></tr>
        </table>
        """,
        20: """
        <table>
          <tr><td><a href="/job/Dublin-Infrastructure-Engineer/3/">Infrastructure Engineer</a></td><td>Dublin, IE</td></tr>
          <tr><td><a href="/job/Cork-Civil-Engineer/4/">Civil Engineer</a></td><td>Cork, IE</td></tr>
        </table>
        """,
        40: "<html><body>No more jobs</body></html>",
    }

    def fake_request(method, url, **kwargs):
        if "startrow=20" in url:
            return FakeResponse(pages[20])
        if "startrow=40" in url:
            return FakeResponse(pages[40])
        return FakeResponse(pages[0])

    monkeypatch.setattr(source.client, "request", fake_request)
    links = source._discover_links()

    assert len(links) == 2
    assert any("Infrastructure-Engineer" in link for link in links)
    assert any("Civil-Engineer" in link for link in links)
