from __future__ import annotations

import re

from .models import Assessment, Job

POLICY_VERSION = "2026-09-13.6"

HARD_NEGATIVE_TITLE = (
    r"\bintern(ship)?\b",
    r"\bapprentice(ship)?\b",
    r"\bgraduate\b",
    r"\btrainee\b",
    r"\bquantity surveyor\b",
    r"\bmechanical engineer\b",
    r"\belectrical engineer\b",
    r"\bsoftware engineer\b",
    r"\bsite reliability engineer\b",
    r"\barchitect\b",
    r"\bbim (?:coordinator|manager|technician)\b",
)

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

TITLE_FAMILIES: tuple[tuple[str, str, int], ...] = (
    (r"\bhighways? (?:design )?engineer\b", "highway_engineer", 98),
    (r"\broads? (?:design )?engineer\b", "roads_engineer", 97),
    (r"\btransport(?:ation)? engineer\b", "transportation_engineer", 94),
    (r"\bassistant resident engineer\b", "assistant_resident_engineer", 93),
    (r"\bresident engineer\b", "resident_engineer", 96),
    (r"\bcivil design engineer\b", "civil_design_engineer", 95),
    (r"\bcivil site engineer\b", "site_engineer", 95),
    (r"\bsite engineer\b", "site_engineer", 92),
    (r"\bsetting out engineer\b", "setting_out_engineer", 88),
    (r"\binfrastructure engineer\b", "infrastructure_engineer", 91),
    (r"\bcivil project engineer\b", "project_engineer", 92),
    (r"\bproject engineer\b", "project_engineer", 85),
    (r"\bcivil engineer\b", "civil_engineer", 88),
    (r"\bdesign engineer\b", "design_engineer", 78),
    (r"\bsite development engineer\b", "site_development_engineer", 86),
)

CRITICAL_ROLE_FAMILIES = {
    "highway_engineer",
    "roads_engineer",
    "transportation_engineer",
    "resident_engineer",
    "assistant_resident_engineer",
    "civil_design_engineer",
    "site_engineer",
    "setting_out_engineer",
    "infrastructure_engineer",
    "project_engineer",
    "civil_engineer",
    "site_development_engineer",
}

BODY_BONUS = {
    "civil 3d": 5,
    "autocad": 3,
    "highway": 5,
    "roads": 4,
    "road design": 5,
    "horizontal alignment": 5,
    "vertical alignment": 5,
    "alignment design": 4,
    "detailed design": 3,
    "dpr": 4,
    "site supervision": 3,
    "site inspection": 2,
    "quality control": 3,
    "qa/qc": 3,
    "tender": 2,
    "boq": 2,
    "cost estimate": 2,
    "infrastructure": 3,
    "resident engineer": 4,
    "contractor": 2,
    "consultant": 2,
    "utility": 2,
    "road safety": 3,
    "blackspot": 3,
}

GAP_TERMS = {
    "structural calculations": "role is structurally specialised",
    "geotechnical design": "role is geotechnically specialised",
    "revit": "Revit is requested but is not in the current CV",
    "tekla": "Tekla is requested but is not in the current CV",
}


def _has(pattern: str, value: str) -> bool:
    return bool(re.search(pattern, value, re.I))


def _salary_numbers(text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(r"€\s*([0-9]{2,3})(?:[,.]([0-9]{3}))?\s*([kK])?", text or ""):
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
    """Use explicit salary fields or salary-context snippets, not arbitrary project euro values."""
    if job.salary_text.strip():
        return job.salary_text
    snippets: list[str] = []
    for match in re.finditer(r"salary|remuneration|pay range|per annum|p\\.?a\\.?", job.text, re.I):
        start = max(0, match.start() - 100)
        end = min(len(job.text), match.end() + 160)
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
    """Extract explicit employment-contract duration, avoiding unrelated project-value numbers."""
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


def preliminary_assessment(job: Job, profile: dict) -> Assessment:
    title = job.title.casefold()
    text = f"{job.title} {job.company} {job.location} {job.text}".casefold()
    location = job.location.casefold().strip()

    if not profile.get("include_northern_ireland", False) and any(
        x in f"{location} {job.text[:500].casefold()}" for x in ["belfast", "northern ireland"]
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

    for pattern in HARD_NEGATIVE_TITLE:
        if _has(pattern, title):
            return Assessment(
                False, 0, "other", "unclear", "low",
                "The title is outside the target experienced civil/highway engineering profile.",
                hard_reject=True,
            )

    role_family = "other"
    base = 0
    for pattern, family, score in TITLE_FAMILIES:
        if _has(pattern, title) and score > base:
            role_family, base = family, score

    if base == 0:
        if "engineer" in title and any(x in text for x in ["civil", "road", "highway", "transport", "infrastructure", "construction"]):
            role_family, base = "civil_infrastructure_engineer", 70
        else:
            return Assessment(
                False, 0, "other", "unclear", "low",
                "No sufficiently strong civil-engineering occupational identity was found.",
            )

    score = base
    strengths: list[str] = []
    gaps: list[str] = []
    for phrase, bonus in BODY_BONUS.items():
        if phrase in text:
            score += bonus
            strengths.append(phrase)

    required_years = _required_years(text)
    candidate_years = float(profile.get("years_experience", 0))
    if required_years is not None:
        if required_years > candidate_years + 2:
            score = min(score - 18, 70)
            gaps.append(f"posting appears to require about {required_years}+ years of experience")
        elif required_years > candidate_years:
            score = min(score - 8, 86)
            gaps.append(f"posting asks for {required_years}+ years; candidate has about {candidate_years:g}")
        else:
            strengths.append(f"experience threshold ({required_years}+ years) is within range")

    for phrase, gap in GAP_TERMS.items():
        if phrase in text:
            score -= 5
            gaps.append(gap)

    mandatory_chartered = (
        _has(r"(?:must be|must hold|is required|required:)\s+(?:a\s+)?chartered", text)
        or _has(r"chartered (?:engineer(?: status)?|status) (?:is )?(?:required|essential|mandatory)", text)
    )
    if mandatory_chartered:
        score = min(score - 14, 70)
        gaps.append("Chartered Engineer status appears mandatory")
    elif "chartered" in text:
        gaps.append("Chartered status is mentioned; verify whether it is essential or only desirable")
        score -= 3

    mandatory_irish_experience = _has(r"irish experience.{0,30}(?:required|essential|mandatory)", text)
    if mandatory_irish_experience:
        score = min(score - 10, 70)
        gaps.append("Irish experience appears mandatory")

    if any(x in text for x in ["visa sponsorship", "employment permit support", "work permit support", "relocation support", "critical skills permit"]):
        score += 8
        strengths.append("explicit relocation/work-permit support")

    contract_months = _contract_months(text)
    permanent = "permanent" in text or "full time permanent" in text
    if contract_months is not None and contract_months < 12:
        return Assessment(
            False,
            min(max(score, 0), 55),
            role_family,
            "short_contract_under_12_months",
            "low",
            "The advertised contract is under 12 months, making it a poor relocation target for a first-time Ireland employment-permit move.",
            strengths=list(dict.fromkeys(strengths))[:8],
            gaps=list(dict.fromkeys(gaps + [f"contract duration is only {contract_months} months"]))[:6],
            hard_reject=True,
            source="relocation-gate",
        )

    salaries = _salary_numbers(_salary_evidence_text(job))
    salary_floor = min(salaries) if salaries else None
    critical = role_family in CRITICAL_ROLE_FAMILIES
    permit = "critical_skills_plausible" if critical else "general_or_unclear"
    relocation = "high" if critical else "medium"

    critical_threshold = int(profile["critical_skills_salary_eur"])
    general_threshold = int(profile["general_permit_salary_eur"])
    source_names = {part.strip().casefold() for part in job.source.split("+")}
    public_sector = bool(source_names & {"publicjobs", "localgovernmentjobs"})

    if salary_floor is not None:
        if salary_floor >= critical_threshold and critical:
            permit = "critical_skills_salary_met"
            strengths.append("advertised salary meets the current Critical Skills threshold")
        elif salary_floor >= general_threshold:
            permit = "general_permit_salary_met"
            relocation = "medium"
            score -= 3
            gaps.append("salary appears below the standard Critical Skills threshold")
        elif not public_sector:
            permit = "salary_below_normal_permit_threshold"
            relocation = "low"
            score -= 22
            gaps.append("advertised salary appears below the normal General Employment Permit threshold")
        else:
            permit = "public_sector_pay_scale_review"
            relocation = "medium"
            gaps.append("public-sector pay-scale exception needs confirmation")

    if contract_months is not None:
        if contract_months < 24:
            if permit != "salary_below_normal_permit_threshold":
                permit = "general_permit_duration_plausible"
            relocation = "medium"
            score -= 8
            gaps.append(
                f"{contract_months}-month offer is too short for a Critical Skills permit; General Employment Permit route must be assessed"
            )
        else:
            strengths.append("2+ year duration appears compatible with Critical Skills permit duration")
    elif permanent:
        strengths.append("permanent role")
        score += 2
    elif critical and ("fixed term" in text or "fixed-term" in text or "contract" in text):
        permit = "critical_skills_duration_unconfirmed"
        relocation = "medium"
        score -= 5
        gaps.append("fixed-term duration is unclear; Critical Skills requires a 2-year job offer")

    score = max(0, min(100, score))
    matched = score >= int(profile["minimum_target_score"])
    if permit == "salary_below_normal_permit_threshold" or mandatory_chartered or mandatory_irish_experience:
        matched = False

    return Assessment(
        matched=matched,
        score=score,
        role_family=role_family,
        permit_path=permit,
        relocation_fit=relocation,
        reason="Profile fit is based on civil/highway role identity, CV-aligned duties and Ireland employment-permit feasibility.",
        strengths=list(dict.fromkeys(strengths))[:8],
        gaps=list(dict.fromkeys(gaps))[:6],
        source="deterministic",
    )


def should_ai_refine(job: Job, assessment: Assessment) -> bool:
    """Use AI only where deterministic evidence leaves a meaningful decision risk."""
    if assessment.hard_reject or assessment.score < 72:
        return False

    title = job.title.casefold()
    seniority_needs_review = any(term in title for term in ("senior", "principal", "lead", "associate"))
    requirement_gap = any(
        phrase in gap.casefold()
        for gap in assessment.gaps
        for phrase in ("posting asks for", "require about", "chartered", "irish experience")
    )
    ambiguous_family = assessment.role_family in {
        "project_engineer",
        "design_engineer",
        "civil_infrastructure_engineer",
        "site_engineer",
        "infrastructure_engineer",
    }
    permit_uncertain = assessment.permit_path in {
        "general_or_unclear",
        "critical_skills_duration_unconfirmed",
        "public_sector_pay_scale_review",
    }
    near_notification_boundary = 72 <= assessment.score <= 86

    return (
        seniority_needs_review
        or requirement_gap
        or ambiguous_family
        or permit_uncertain
        or near_notification_boundary
    )


def enforce_final_policy(assessment: Assessment, profile: dict) -> Assessment:
    """Do not let AI bypass the agent's minimum precision/relocation gates."""
    if assessment.hard_reject:
        assessment.matched = False
        return assessment
    if assessment.source == "ai-refined":
        minimum = int(profile["minimum_target_score"])
        if assessment.score < minimum or assessment.permit_path == "not_eligible" or assessment.relocation_fit == "low":
            assessment.matched = False
    return assessment
