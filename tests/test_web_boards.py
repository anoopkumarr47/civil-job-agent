from civil_job_agent.sources.web_boards import ConfiguredWebBoard


def _jobsireland_board():
    return ConfiguredWebBoard(
        {
            "name": "JobsIreland",
            "allowed_hosts": ["jobsireland.ie"],
            "job_link_patterns": ["job-details"],
        },
        request_timeout=1,
        max_links=10,
    )


def test_blank_job_id_is_rejected():
    board = _jobsireland_board()
    assert not board._looks_like_job("https://jobsireland.ie/en-US/job-Details?id=")


def test_real_job_id_is_accepted():
    board = _jobsireland_board()
    assert board._looks_like_job("https://jobsireland.ie/en-US/job-Details?id=2455502")
