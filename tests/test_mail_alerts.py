from civil_job_agent.sources.mail_alerts import _title_from_alert


def test_alert_uses_link_title_when_specific():
    assert _title_from_alert("Highway Engineer", "Highway Engineer Example Ltd") == "Highway Engineer"


def test_alert_recovers_title_from_generic_view_job_button():
    title = _title_from_alert("View job", "New match: Senior Civil Design Engineer — Dublin — Example Ltd")
    assert title.casefold() == "senior civil design engineer"
