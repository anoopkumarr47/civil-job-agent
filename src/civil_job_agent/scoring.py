from __future__ import annotations

import re

from .models import Assessment, Job
from .relevance import (
    CIVIL,
    NON_CIVIL,
    UNCLEAR,
    classify_civil_domain,
    is_clear_non_civil_title,
    is_early_career_title,
    is_plausible_target_title,
    role_family_for_title,
)

POLICY_VERSION = "2026-09-14.2"

RIGHT_TO_WORK_NEGATIVE = (
    r"must already have (?:the )?right to work in ireland",
    r"must have (?:an )?existing right to work in ireland",
    r"must be eligible to work in ireland without sponsorship",
    r"no (?:visa )?sponsorship",
    r"unable to sponsor",
    r"sponsorship (?:is )?not available",
    r"cannot sponsor",
    r"eu passport required",
    r"eea passport required",
    r"we (?:do not|don't) (?:offer|provide) (?:visa )?sponsorship",
    r"(?:visa )?sponsorship (?:cannot|can't|will not|won't) be (?:offered|provided)",
    r"applicants? must (?:already )?(?:have|hold) (?:valid )?(?:permission|authori[sz]ation|right) to work in ireland",
    r"must be (?:legally )?(?:entitled|authori[sz]ed) to work in ireland",
    r"must hold (?:a )?(?:valid )?(?:irish|ireland) work permit",
    r"stamp 4 (?:is )?required",
)

CRITICAL_ROLE_FAMILIES = {
    "highway_engineer",
    "roads_engineer",
    "transportation_engineer",
    "traffic_engineer",
    "pavement_engineer",
    "resident_engineer",
    "assistant_resident_engineer",
    "civil_design_engineer",
    "site_engineer",
    "setting_out_engineer",
    "section_engineer",
    "infrastructure_engineer",
    "project_engineer",
    "civil_engineer",
    "site_development_engineer",
    "public_realm_engineer",
    "rail_engineer",
    "drainage_engineer",
    "water_engineer",
    "utilities_engineer",
}

BODY_BONUS = {
    "civil 3d": 5,
    "autocad": 2,
    "highway": 5,
    "roads": 4,
    "road design": 5,
    "horizontal alignment": 5,
    "vertical alignment": 5,
    "alignment design": 4,
    "geometric design": 4,
    "detailed design": 2,
    "dpr": 4,
    "site supervision": 3,
    "site inspection": 2,
    "quality control": 2,
    "qa/qc": 2,
    "tender": 2,
    "boq": 2,
    "cost estimate": 2,
    "transport infrastructure": 4,
    "resident engineer": 4,
    "contractor supervision": 3,
    "contractor coordination": 2,
    "consultant coordination": 2,
    "utilities coordination": 2,
    "road safety": 3,
    "blackspot": 3,
    "drainage": 3,
    "earthworks": 3,
    "pavement": 3,
    "public realm": 3,
    "setting out": 3,
}

SPECIALIST_GAPS = {
    "structural calculations": "role has a structural-design specialism outside the strongest CV evidence",
    "geotechnical design": "role has a geotechnical-design specialism outside the strongest CV evidence",
    "revit": "Revit is requested but is not in the current CV",
    "tekla": "Tekla is requested but is not in the current CV",
    "microstation": "MicroStation is requested but is not in the current CV",
    "openroads": "OpenRoads is requested but is not in the current CV",
}

FOREIGN_LOCATION_TERMS = (
    "united kingdom", "england", "scotland", "wales", "middle east", "turkey", "australia",
    "new zealand", "united states", "usa", "canada", "india", "uae", "dubai", "abu dhabi",
    "saudi arabia", "qatar", "singapore", "hong kong", "germany", "france", "netherlands",
    "spain", "italy", "belgium", "sweden", "norway", "denmark", "finland", "poland",
)

IRISH_LOCATION_TERMS = (
    "ireland", "dublin", "cork", "galway", "limerick", "waterford", "kilkenny", "kildare",
    "wicklow", "meath", "louth", "laois", "offaly", "westmeath", "wexford", "tipperary",
    "clare", "kerry", "mayo", "sligo", "leitrim", "roscommon", "cavan", "monaghan",
    "donegal", "longford", "carlow", "athlone",
)


def _has(pattern: str, value: str) -> bool:
    return bool(re.search(pattern, value, re.I))


def _salary_numbers(text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(
        r"(?:€|EUR\s*)\s*([0-9]{2,3})(?:[,.]([0-9]{3}))?\s*([kK])?",
        text or "",
        re.I,
    ):
        first, second, k = match.groups()
        if second:
            value = int(first) * 1000 + int(second)
        else:
            value = int(first)
            if k or value < 1000:
                value *= 1000
        if 20_000 <= value <= 250_000:
            values.append(value)
    return values


def _salary_evidence_text(job: Job) -> str:
    if job.salary_text.strip():
        return job.salary_text
    snippets: list[str] = []
    for match in re.finditer(r"salary|remuneration|pay range|per annum|p\.?a\.?", job.text, re.I):
        start = max(0, match.start() - 100)
        end = min(len(job.text), match.end() + 180)
        snippets.append(job.text[start:end])
    return " ".join(snippets)


def _required_years(text: str) -> int | None:
    numbers: list[int] = []
    for pattern in (
        r"(?:minimum|min\.?|at least)\s+(\d{1,2})\+?\s+years?",
        r"(\d{1,2})\+\s+years?\s+(?:of\s+)?experience",
        r"experience\s+of\s+(\d{1,2})\+?\s+years?",
        r"(?:minimum|min\.?|at least)\s+(\d{1,2})\s+years['’]?\s+(?:post[- ]graduate\s+)?experience",
    ):
        numbers.extend(int(x) for x in re.findall(pattern, text, re.I))
    return max(numbers) if numbers else None


def _contract_months(text: str) -> int | None:
    values: list[int] = []
    patterns = (
        r"(?:contract\s+duration|duration)\s*:?\s*(\d{1,2})\s*[- ]?months?",
        r"(\d{1,2})\s*[- ]month\s+(?:fixed[- ]term\s+)?contract",
        r"(?:fixed[- ]term\s+)?contract(?:\s+(?:role|position))?\s+(?:for|of)\s+(?:approximately\s+)?(\d{1,2})\s*months?",
        r"(?:role|position|vacancy).{0,120}?for\s+(?:approximately\s+)?(\d{1,2})\s*months?",
        r"for\s+approximately\s+(\d{1,2})\s*months?",
    )
    for pattern in patterns:
        values.extend(int(x) for x in re.findall(pattern, text, re.I | re.S))
    return min(values) if values else None


def preliminary_assessment(job: Job, profile: dict) -> Assessment:
    title = job.title.casefold()
    text = f"{job.title} {job.company} {job.location} {job.text}".casefold()
    location = job.location.casefold().strip()

    if not profile.get("include_northern_ireland", False) and any(
        x in f"{location} {job.text[:700].casefold()}" for x in ("belfast", "northern ireland")
    ):
        return Assessment(
            False, 0, "other", "not_eligible", "low",
            "Northern Ireland uses the UK immigration system, not the Republic of Ireland employment-permit route.",
            hard_reject=True,
        )

    if location and location not in {"ireland", "republic of ireland", "remote", "hybrid"}:
        has_irish = any(term in location for term in IRISH_LOCATION_TERMS)
        has_foreign = any(term in location for term in FOREIGN_LOCATION_TERMS)
        if has_foreign and not has_irish:
            return Assessment(
                False, 0, "other", "not_eligible", "low",
                "The vacancy location is outside the Republic of Ireland.",
                hard_reject=True,
            )

    for pattern in RIGHT_TO_WORK_NEGATIVE:
        if _has(pattern, text):
            return Assessment(
                False, 0, "other", "not_eligible", "low",
                "The posting explicitly rules out the work-permit/sponsorship route needed for an India-based applicant.",
                hard_reject=True,
            )

    if is_early_career_title(job.title):
        return Assessment(
            False, 0, "other", "unclear", "low",
            "The vacancy is explicitly graduate, intern, apprentice, trainee or placement level.",
            hard_reject=True,
        )

    domain = classify_civil_domain(job.title, job.text)
    if domain.domain == NON_CIVIL or is_clear_non_civil_title(job.title):
        return Assessment(
            False, 0, "other", "not_eligible", "low",
            "The vacancy is an engineering/technology role outside the civil/construction domain.",
            gaps=[f"non-civil signals: {', '.join(domain.non_civil_terms[:4])}"] if domain.non_civil_terms else [],
            hard_reject=True,
            source="domain-gate",
        )

    role_family, base = role_family_for_title(job.title)
    if base == 0:
        if domain.domain == CIVIL and "engineer" in title:
            role_family, base = "civil_infrastructure_engineer", 68
        elif domain.domain == CIVIL and any(term in title for term in ("inspector", "site agent", "clerk of works")):
            role_family, base = "civil_site_role", 66
        elif domain.domain == UNCLEAR and is_plausible_target_title(job.title):
            role_family, base = "ambiguous_engineering_role", 62
        else:
            return Assessment(
                False, 0, "other", "unclear", "low",
                "No sufficiently plausible civil-engineering occupational identity was found.",
            )

    # Ambiguous titles such as Infrastructure Engineer must prove their domain from the
    # description; never let the title alone create a high-confidence match.
    if domain.domain == UNCLEAR:
        base = min(base, 72)

    score = base
    strengths: list[str] = []
    gaps: list[str] = []

    if domain.domain == CIVIL:
        score += min(8, max(0, domain.civil_score // 3))
        if domain.civil_terms:
            strengths.append("civil-domain evidence: " + ", ".join(domain.civil_terms[:4]))
    else:
        gaps.append("civil domain is not explicit; AI review required")

    for phrase, bonus in BODY_BONUS.items():
        if phrase in text:
            score += bonus
            strengths.append(phrase)

    required_years = _required_years(text)
    candidate_years = float(profile.get("years_experience", 0))
    if required_years is not None:
        if required_years > candidate_years + 3:
            score = min(score - 18, 70)
            gaps.append(f"posting appears to require about {required_years}+ years of experience")
        elif required_years > candidate_years:
            score = min(score - 7, 86)
            gaps.append(f"posting asks for {required_years}+ years; candidate has about {candidate_years:g}")
        else:
            strengths.append(f"experience threshold ({required_years}+ years) is within range")

    for phrase, gap in SPECIALIST_GAPS.items():
        if phrase in text:
            score -= 4
            gaps.append(gap)

    # Do not reject all structural/geotechnical jobs by title: they are civil-domain roles
    # and some multidisciplinary infrastructure postings may still fit. Penalise specialization.
    if "structural engineer" in title:
        score = min(score - 10, 72)
        gaps.append("structural specialism is outside the strongest highways/roads CV evidence")
    if "geotechnical engineer" in title:
        score = min(score - 10, 72)
        gaps.append("geotechnical specialism is outside the strongest highways/roads CV evidence")

    mandatory_chartered = (
        _has(r"(?:must be|must hold|is required|required:)\s+(?:a\s+)?chartered", text)
        or _has(r"chartered (?:engineer(?: status)?|status) (?:is )?(?:required|essential|mandatory)", text)
    )
    if mandatory_chartered:
        score = min(score - 14, 70)
        gaps.append("Chartered Engineer status appears mandatory")
    elif "chartered" in text:
        gaps.append("Chartered status is mentioned; verify whether essential or desirable")
        score -= 2

    mandatory_irish_experience = _has(r"irish experience.{0,35}(?:required|essential|mandatory)", text)
    if mandatory_irish_experience:
        score = min(score - 10, 70)
        gaps.append("Irish experience appears mandatory")

    if any(
        x in text
        for x in (
            "visa sponsorship",
            "employment permit support",
            "work permit support",
            "relocation support",
            "critical skills permit",
        )
    ):
        score += 8
        strengths.append("explicit relocation/work-permit support")

    contract_months = _contract_months(text)
    permanent = "permanent" in text or "full time permanent" in text
    if contract_months is not None and contract_months < 12:
        return Assessment(
            False,
            min(max(score, 0), 55),
            role_family,
            "not_eligible",
            "low",
            "The advertised contract is under 12 months and is a poor first-relocation target.",
            strengths=list(dict.fromkeys(strengths))[:8],
            gaps=list(dict.fromkeys(gaps + [f"contract duration is only {contract_months} months"]))[:6],
            hard_reject=True,
            source="relocation-gate",
        )

    critical = domain.domain == CIVIL and role_family in CRITICAL_ROLE_FAMILIES
    permit = "critical_skills" if critical else "unclear"
    relocation = "high" if critical else "medium"

    salaries = _salary_numbers(_salary_evidence_text(job))
    salary_floor = min(salaries) if salaries else None
    critical_threshold = int(profile["critical_skills_salary_eur"])
    general_threshold = int(profile["general_permit_salary_eur"])
    source_names = {part.strip().casefold() for part in job.source.split("+")}
    public_sector = bool(source_names & {"publicjobs", "localgovernmentjobs"})

    if salary_floor is not None:
        if salary_floor >= critical_threshold and critical:
            strengths.append("advertised salary meets the configured Critical Skills threshold")
        elif salary_floor >= general_threshold:
            permit = "general"
            relocation = "medium"
            score -= 3
            if critical:
                gaps.append("salary appears below the configured Critical Skills threshold")
        elif not public_sector:
            permit = "not_eligible"
            relocation = "low"
            score -= 22
            gaps.append("advertised salary appears below the normal General Employment Permit threshold")
        else:
            permit = "unclear"
            relocation = "medium"
            gaps.append("public-sector pay-scale treatment needs confirmation")

    if contract_months is not None:
        if contract_months < 24:
            if permit != "not_eligible":
                permit = "general"
            relocation = "medium"
            score -= 8
            gaps.append(
                f"{contract_months}-month offer is too short for the usual Critical Skills two-year offer requirement"
            )
        else:
            strengths.append("2+ year duration appears compatible with the Critical Skills offer-duration rule")
    elif permanent:
        strengths.append("permanent role")
        score += 2
    elif critical and ("fixed term" in text or "fixed-term" in text or "contract" in text):
        permit = "unclear"
        relocation = "medium"
        score -= 5
        gaps.append("fixed-term duration is unclear; verify the two-year Critical Skills offer requirement")

    score = max(0, min(100, score))
    matched = (
        domain.domain == CIVIL
        and score >= int(profile["minimum_target_score"])
        and permit != "not_eligible"
        and relocation != "low"
        and not mandatory_chartered
        and not mandatory_irish_experience
    )

    return Assessment(
        matched=matched,
        score=score,
        role_family=role_family,
        permit_path=permit,
        relocation_fit=relocation,
        reason=(
            "Fit combines verified civil-domain evidence, role/CV alignment and Ireland employment-permit feasibility."
            if domain.domain == CIVIL
            else "The title is potentially relevant but the civil domain is ambiguous and requires AI adjudication."
        ),
        strengths=list(dict.fromkeys(strengths))[:8],
        gaps=list(dict.fromkeys(gaps))[:6],
        source="deterministic",
    )


def should_ai_refine(job: Job, assessment: Assessment) -> bool:
    if assessment.hard_reject or assessment.role_family == "other":
        return False
    # Ambiguous-domain roles are intentionally reviewed at a lower score to maximize recall.
    return assessment.score >= 55


def enforce_final_policy(assessment: Assessment, profile: dict) -> Assessment:
    if assessment.hard_reject:
        assessment.matched = False
        return assessment
    if assessment.source.startswith("ai-"):
        minimum = int(profile["minimum_target_score"])
        if (
            assessment.score < minimum
            or assessment.permit_path == "not_eligible"
            or assessment.relocation_fit == "low"
        ):
            assessment.matched = False
    return assessment
