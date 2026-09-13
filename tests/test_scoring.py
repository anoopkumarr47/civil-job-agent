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
    assert should_ai_refine(job("Project Engineer", "civil roads infrastructure"), result)

def test_explicit_foreign_location_is_rejected(profile):
    result = preliminary_assessment(job("Civil Engineer", "civil infrastructure", location="Manchester, United Kingdom"), profile)
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_irish_location_is_not_rejected(profile):
    result = preliminary_assessment(job("Civil Engineer", "civil infrastructure", location="Dublin, Ireland"), profile)
    assert not result.hard_reject


def test_project_value_is_not_misread_as_salary(profile):
    result = preliminary_assessment(
        job(
            "Civil Engineer",
            "Civil infrastructure project valued at €50,000 with roads and site supervision.",
            salary="",
        ),
        profile,
    )
    assert result.permit_path == "critical_skills_plausible"


def test_explicit_salary_context_is_used(profile):
    result = preliminary_assessment(
        job(
            "Civil Engineer",
            "Salary €50,000 per annum. Civil infrastructure and roads.",
            salary="",
        ),
        profile,
    )
    assert result.permit_path == "critical_skills_salary_met"


def test_additional_no_sponsorship_wording_is_rejected(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "We do not offer visa sponsorship for this position."),
        profile,
    )
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_generic_site_engineer_requires_context_adjudication(profile):
    result = preliminary_assessment(job("Site Engineer", "construction project delivery"), profile)
    assert should_ai_refine(job("Site Engineer", "construction project delivery"), result)


def test_generic_infrastructure_engineer_requires_context_adjudication(profile):
    result = preliminary_assessment(job("Infrastructure Engineer", "project delivery"), profile)
    assert should_ai_refine(job("Infrastructure Engineer", "project delivery"), result)


def test_current_2026_critical_skills_threshold(profile):
    below = preliminary_assessment(job("Civil Engineer", "Salary €40,908 per annum. Civil roads.", salary="€40,908"), profile)
    at_threshold = preliminary_assessment(job("Civil Engineer", "Salary €40,909 per annum. Civil roads.", salary="€40,909"), profile)
    assert below.permit_path != "critical_skills_salary_met"
    assert at_threshold.permit_path == "critical_skills_salary_met"


def test_short_contract_is_relocation_reject(profile):
    candidate = job(
        "Resident Engineer",
        "Civil roads. This is a 9-month fixed-term contract with site supervision.",
    )
    result = preliminary_assessment(candidate, profile)
    assert result.hard_reject
    assert not result.matched
    assert result.permit_path == "short_contract_under_12_months"


def test_contract_under_two_years_downgrades_critical_skills(profile):
    candidate = job(
        "Resident Engineer",
        "Civil roads. Contract duration: 18 months. Site supervision and contractor coordination.",
        salary="€55,000",
    )
    result = preliminary_assessment(candidate, profile)
    assert result.permit_path == "general_permit_duration_plausible"
    assert result.relocation_fit == "medium"
    assert any("too short for a Critical Skills permit" in gap for gap in result.gaps)


def test_senior_title_forces_ai_review(profile):
    candidate = job("Senior Transportation Engineer", "Civil roads transport infrastructure")
    result = preliminary_assessment(candidate, profile)
    assert should_ai_refine(candidate, result)


def test_mandatory_chartered_status_blocks_match(profile):
    candidate = job(
        "Civil Engineer",
        "Civil roads infrastructure. Chartered Engineer status is required.",
        salary="€60,000",
    )
    result = preliminary_assessment(candidate, profile)
    assert not result.matched
    assert any("mandatory" in gap.casefold() for gap in result.gaps)


def test_mandatory_irish_experience_blocks_match(profile):
    candidate = job(
        "Civil Engineer",
        "Civil roads infrastructure. Irish experience is mandatory.",
        salary="€60,000",
    )
    result = preliminary_assessment(candidate, profile)
    assert not result.matched
    assert any("irish experience" in gap.casefold() for gap in result.gaps)


def test_clear_high_confidence_highway_role_skips_ai(profile):
    candidate = job(
        "Highway Engineer",
        "Civil 3D road design horizontal alignment vertical alignment permanent",
    )
    result = preliminary_assessment(candidate, profile)
    assert result.score >= 92
    assert not should_ai_refine(candidate, result)


def test_low_scoring_role_does_not_burn_ai_quota(profile):
    candidate = job(
        "Project Engineer",
        "Minimum 15 years experience in civil infrastructure.",
    )
    result = preliminary_assessment(candidate, profile)
    assert result.score < 68
    assert not should_ai_refine(candidate, result)
