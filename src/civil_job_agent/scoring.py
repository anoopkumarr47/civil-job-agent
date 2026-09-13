from __future__ import annotations

import re

from .models import Assessment, Job

POLICY_VERSION = "2026-09-13.2"

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


def _required_years(text: str) -> int | None:
    numbers: list[int] = []
    for pattern in (
        r"(?:minimum|min\.?|at least)\s+(\d{1,2})\+?\s+years?",
        r"(\d{1,2})\+\s+years?\s+(?:of\s+)?experience",
        r"experience\s+of\s+(\d{1,2})\+?\s+years?",
    ):
        numbers.extend(int(x) for x in re.findall(pattern, text, re.I))
    return max(numbers) if numbers else None


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
        if required_years > candidate_years + 3:
            score -= 18
            gaps.append(f"posting appears to require about {required_years}+ years of experience")
        elif required_years > candidate_years:
            score -= 8
            gaps.append(f"posting asks for {required_years}+ years; candidate has about {candidate_years:g}")
        else:
            strengths.append(f"experience threshold ({required_years}+ years) is within range")

    for phrase, gap in GAP_TERMS.items():
        if phrase in text:
            score -= 5
            gaps.append(gap)

    if _has(r"(?:must be|must hold|is required|required:)\s+(?:a\s+)?chartered", text) or _has(r"chartered (?:engineer|status) (?:is )?(?:required|essential)", text):
        score -= 14
        gaps.append("Chartered Engineer status appears mandatory")
    elif "chartered" in text:
        gaps.append("Chartered status is mentioned; verify whether it is essential or only desirable")
        score -= 3

    if _has(r"irish experience.{0,30}(?:required|essential|mandatory)", text):
        score -= 10
        gaps.append("Irish experience appears mandatory")

    if any(x in text for x in ["visa sponsorship", "employment permit support", "work permit support", "relocation support", "critical skills permit"]):
        score += 8
        strengths.append("explicit relocation/work-permit support")

    salaries = _salary_numbers(f"{job.salary_text} {job.text[:2200]}")
    salary_floor = min(salaries) if salaries else None
    critical = role_family in CRITICAL_ROLE_FAMILIES
    permit = "critical_skills_plausible" if critical else "general_or_unclear"
    relocation = "high" if critical else "medium"

    critical_threshold = int(profile["critical_skills_salary_eur"])
    general_threshold = int(profile["general_permit_salary_eur"])
    public_sector = job.source.casefold() in {"publicjobs", "localgovernmentjobs"}

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

    if "permanent" in text or "full time permanent" in text:
        score += 2
        strengths.append("permanent role")
    if re.search(r"\b(?:24|2[4-9]|3\d)\s+months\b|\b2\+?\s+years?\s+(?:contract|fixed term)", text):
        strengths.append("2+ year duration appears compatible with Critical Skills permit duration")

    score = max(0, min(100, score))
    matched = score >= int(profile["minimum_target_score"])
    if permit == "salary_below_normal_permit_threshold":
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


def should_ai_refine(assessment: Assessment) -> bool:
    if assessment.hard_reject:
        return False
    if assessment.score < 60:
        return False
    return assessment.score < 92 or assessment.role_family in {"project_engineer", "design_engineer", "civil_infrastructure_engineer"}
