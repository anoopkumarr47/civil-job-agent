from civil_job_agent.relevance import CIVIL, NON_CIVIL, UNCLEAR, classify_civil_domain


def test_it_infrastructure_is_non_civil():
    evidence = classify_civil_domain(
        "Infrastructure Engineer",
        "Build AWS Azure cloud infrastructure using Terraform Kubernetes networking and Linux servers.",
    )
    assert evidence.domain == NON_CIVIL


def test_physical_infrastructure_is_civil():
    evidence = classify_civil_domain(
        "Infrastructure Engineer",
        "Civil engineering roads drainage earthworks transport infrastructure and Civil 3D design.",
    )
    assert evidence.domain == CIVIL


def test_sparse_generic_infrastructure_remains_unclear():
    evidence = classify_civil_domain(
        "Infrastructure Engineer",
        "Coordinate projects, stakeholders and delivery programmes.",
    )
    assert evidence.domain == UNCLEAR


def test_site_engineer_title_establishes_civil_domain_when_body_is_sparse():
    evidence = classify_civil_domain(
        "Site Engineer",
        "Coordinate construction activities and inspections.",
    )
    assert evidence.domain == CIVIL
