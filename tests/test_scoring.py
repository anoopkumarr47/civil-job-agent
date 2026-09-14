import pytest

from civil_job_agent.models import Job
from civil_job_agent.scoring import preliminary_assessment, should_ai_refine


def job(title, text="", salary="", source="test", location="Dublin, Ireland", url="https://example/jobs/1"):
    return Job(source, url, title, "Example", location, text, salary)


def test_highway_role_is_top_match(profile):
    result = preliminary_assessment(
        job("Highway Engineer", "Civil 3D road design horizontal and vertical alignment tender transport infrastructure"),
        profile,
    )
    assert result.matched
    assert result.score >= 95


def test_site_engineer_is_relocation_plausible(profile):
    result = preliminary_assessment(
        job("Site Engineer", "civil engineering roads construction site supervision quality control permanent"),
        profile,
    )
    assert result.matched
    assert result.permit_path == "critical_skills"


@pytest.mark.parametrize("title", ["Graduate Civil Engineer", "Civil Engineering Intern", "Civil Engineer Placement"])
def test_early_career_titles_are_hard_rejected(profile, title):
    result = preliminary_assessment(job(title, "roads civil infrastructure"), profile)
    assert result.hard_reject
    assert not result.matched


@pytest.mark.parametrize(
    ("title", "text"),
    [
        ("Infrastructure Engineer", "AWS Azure Terraform Kubernetes cloud infrastructure networking"),
        ("Cloud Infrastructure Engineer", "Linux AWS Kubernetes Terraform DevOps"),
        ("Network Infrastructure Engineer", "Cisco LAN WAN firewalls network infrastructure"),
        ("Software Engineer", "microservices cloud software development"),
        ("Mechanical Engineer", "mechanical systems manufacturing"),
    ],
)
def test_non_civil_engineering_false_positives_are_hard_rejected(profile, title, text):
    result = preliminary_assessment(job(title, text), profile)
    assert result.hard_reject
    assert not result.matched
    assert result.source == "domain-gate"


def test_civil_infrastructure_engineer_with_generic_title_is_kept(profile):
    candidate = job(
        "Infrastructure Engineer",
        "Civil engineering transport infrastructure roads drainage earthworks Civil 3D site inspection",
    )
    result = preliminary_assessment(candidate, profile)
    assert not result.hard_reject
    assert should_ai_refine(candidate, result)
    assert result.role_family == "infrastructure_engineer"


def test_sparse_infrastructure_engineer_is_ambiguous_not_false_match(profile):
    candidate = job("Infrastructure Engineer", "Project delivery and stakeholder coordination")
    result = preliminary_assessment(candidate, profile)
    assert not result.hard_reject
    assert not result.matched
    assert result.score <= 72
    assert should_ai_refine(candidate, result)


def test_structural_role_is_not_silently_dropped(profile):
    candidate = job(
        "Structural Engineer",
        "Civil engineering infrastructure bridge design site inspection concrete construction",
    )
    result = preliminary_assessment(candidate, profile)
    assert not result.hard_reject
    assert should_ai_refine(candidate, result)
    assert any("structural" in gap.casefold() for gap in result.gaps)


def test_right_to_work_restriction_is_hard_reject(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "Civil roads. Must already have the right to work in Ireland. No sponsorship."),
        profile,
    )
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_low_salary_blocks_private_sector_match(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "civil engineering roads", "€32,000"),
        profile,
    )
    assert not result.matched
    assert result.relocation_fit == "low"
    assert result.permit_path == "not_eligible"


def test_public_sector_low_salary_is_not_automatically_rejected(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "civil engineering public roads", "€35,000", source="LocalGovernmentJobs"),
        profile,
    )
    assert result.permit_path == "unclear"
    assert result.relocation_fit == "medium"


def test_excessive_experience_requirement_is_penalized_but_reviewed(profile):
    candidate = job(
        "Project Engineer",
        "Minimum 12 years experience in civil engineering road infrastructure projects",
    )
    result = preliminary_assessment(candidate, profile)
    assert result.score <= 70
    assert any("12+ years" in gap for gap in result.gaps)
    assert should_ai_refine(candidate, result)


def test_northern_ireland_is_excluded(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "roads", location="Belfast, Northern Ireland"),
        profile,
    )
    assert result.hard_reject
    assert result.permit_path == "not_eligible"


def test_explicit_foreign_location_is_rejected(profile):
    result = preliminary_assessment(
        job("Civil Engineer", "civil infrastructure", location="Manchester, United Kingdom"),
        profile,
    )
    assert result.hard_reject


def test_project_value_is_not_misread_as_salary(profile):
    result = preliminary_assessment(
        job(
            "Civil Engineer",
            "Civil engineering roads project valued at €50,000 with site supervision.",
        ),
        profile,
    )
    assert result.permit_path == "critical_skills"


def test_current_2026_salary_thresholds(profile):
    below = preliminary_assessment(
        job("Civil Engineer", "Civil engineering roads.", salary="€40,908"),
        profile,
    )
    at_threshold = preliminary_assessment(
        job("Civil Engineer", "Civil engineering roads.", salary="€40,909"),
        profile,
    )
    assert below.permit_path == "general"
    assert at_threshold.permit_path == "critical_skills"


def test_short_contract_is_relocation_reject(profile):
    result = preliminary_assessment(
        job("Resident Engineer", "Civil roads. This is a 9-month fixed-term contract with site supervision."),
        profile,
    )
    assert result.hard_reject
    assert not result.matched
    assert result.permit_path == "not_eligible"


def test_contract_under_two_years_downgrades_to_general(profile):
    result = preliminary_assessment(
        job(
            "Resident Engineer",
            "Civil roads. Contract duration: 18 months. Site supervision and contractor coordination.",
            salary="€55,000",
        ),
        profile,
    )
    assert result.permit_path == "general"
    assert result.relocation_fit == "medium"


def test_mandatory_chartered_status_blocks_match(profile):
    result = preliminary_assessment(
        job(
            "Civil Engineer",
            "Civil engineering roads infrastructure. Chartered Engineer status is required.",
            salary="€60,000",
        ),
        profile,
    )
    assert not result.matched
    assert any("mandatory" in gap.casefold() for gap in result.gaps)


def test_mandatory_irish_experience_blocks_match(profile):
    result = preliminary_assessment(
        job(
            "Civil Engineer",
            "Civil engineering roads infrastructure. Irish experience is mandatory.",
            salary="€60,000",
        ),
        profile,
    )
    assert not result.matched


def test_final_policy_applies_to_ai_outputs(profile):
    from civil_job_agent.models import Assessment
    from civil_job_agent.scoring import enforce_final_policy

    low_score = Assessment(True, 70, "civil_engineer", "critical_skills", "high", "fit", source="ai-gemini")
    low_relocation = Assessment(True, 80, "civil_engineer", "critical_skills", "low", "fit", source="ai-consensus")
    assert not enforce_final_policy(low_score, profile).matched
    assert not enforce_final_policy(low_relocation, profile).matched
