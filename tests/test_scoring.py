import pytest

from civil_job_agent.models import Job
from civil_job_agent.scoring import preliminary_assessment, should_ai_refine


def job(title, text="", salary="", source="test", location="Dublin, Ireland"):
    return Job(source, "https://example/jobs/1", title, "Example", location, text, salary)


def test_highway_role_is_top_match(profile):
    result = preliminary_assessment(job("Highway Engineer", "Civil 3D road design horizontal and vertical alignments tender infrastructure"), profile)
    assert result.matched
    assert result.score >= 95


def test_site_engineer_is_relocation_plausible(profile):
    result = preliminary_assessment(job("Site Engineer", "civil roads site supervision quality control permanent"), profile)
    assert result.matched
    assert "critical" in result.permit_path


@pytest.mark.parametrize("title", ["Graduate Civil Engineer", "Civil Engineering Intern", "Quantity Surveyor", "Mechanical Engineer"])
def test_non_target_titles_are_hard_rejected(profile, title):
    result = preliminary_assessment(job(title, "roads civil infrastructure"), profile)
    assert result.hard_reject
    assert not result.matched


def test_right_to_work_restriction_is_hard_reject(profile):
    result = preliminary_assessment(job("Civil Engineer", "Must already have the right to work in Ireland. No sponsorship."), profile)
    assert result.hard_reject
    assert not result.matched


def test_low_salary_blocks_private_sector_match(profile):
    result = preliminary_assessment(job("Civil Engineer", "infrastructure", "€32,000"), profile)
    assert not result.matched
    assert result.relocation_fit == "low"


def test_public_sector_salary_is_not_automatically_hard_rejected(profile):
    result = preliminary_assessment(job("Civil Engineer", "public infrastructure", "€35,000", source="PublicJobs"), profile)
    assert result.permit_path == "public_sector_pay_scale_review"


def test_excessive_experience_requirement_is_penalized(profile):
    result = preliminary_assessment(job("Project Engineer", "Minimum 12 years experience in infrastructure projects"), profile)
    assert result.score < 85
    assert any("12+ years" in gap for gap in result.gaps)


def test_northern_ireland_is_excluded(profile):
    result = preliminary_assessment(job("Civil Engineer", "roads", location="Belfast, Northern Ireland"), profile)
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_generic_project_engineer_is_ai_candidate(profile):
    result = preliminary_assessment(job("Project Engineer", "civil roads infrastructure"), profile)
    assert should_ai_refine(result)

def test_explicit_foreign_location_is_rejected(profile):
    result = preliminary_assessment(job("Civil Engineer", "civil infrastructure", location="Manchester, United Kingdom"), profile)
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_irish_location_is_not_rejected(profile):
    result = preliminary_assessment(job("Civil Engineer", "civil infrastructure", location="Dublin, Ireland"), profile)
    assert not result.hard_reject
