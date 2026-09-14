from __future__ import annotations

import re
from dataclasses import dataclass

from .models import normalize_space

CIVIL = "civil"
NON_CIVIL = "non_civil"
UNCLEAR = "unclear"

# Explicitly civil/construction role titles. These can establish civil domain even when
# a posting body is sparse.
STRONG_CIVIL_TITLE_PATTERNS: tuple[str, ...] = (
    r"\bcivil(?:\s+design|\s+site|\s+project|\s+infrastructure|\s+works)?\s+engineer\b",
    r"\bhighways?\s+(?:design\s+)?engineer\b",
    r"\broads?\s+(?:design\s+)?engineer\b",
    r"\btransport(?:ation)?\s+engineer\b",
    r"\btraffic\s+engineer\b",
    r"\bpavement\s+engineer\b",
    r"\bresident\s+engineer\b",
    r"\bassistant\s+resident\s+engineer\b",
    r"\bsite\s+engineer\b",
    r"\bsetting\s+out\s+engineer\b",
    r"\bsection\s+engineer\b",
    r"\bdrainage\s+engineer\b",
    r"\bwater(?:\s*/\s*wastewater|\s+and\s+wastewater|\s+wastewater)?\s+engineer\b",
    r"\bwastewater\s+engineer\b",
    r"\bpublic\s+realm\s+engineer\b",
    r"\bland\s+development\s+engineer\b",
    r"\bsite\s+development\s+engineer\b",
    r"\bmunicipal\s+engineer\b",
    r"\butilities\s+engineer\b",
    r"\bpermanent\s+way\s+engineer\b",
    r"\btrack\s+engineer\b",
    r"\brail(?:way)?\s+(?:civil\s+)?engineer\b",
    r"\bcivil\s+(?:works\s+)?inspector\b",
    r"\b(?:road|roads|highway|works)\s+inspector\b",
)

# Titles that are plausible for civil work but are also common in IT/manufacturing/MEP.
AMBIGUOUS_TITLE_PATTERNS: tuple[str, ...] = (
    r"\binfrastructure\s+engineer\b",
    r"\bproject\s+engineer\b",
    r"\bdesign\s+engineer\b",
    r"\bconstruction\s+engineer\b",
    r"\bassistant\s+engineer\b",
    r"\bengineer\s*/\s*senior\s+engineer\b",
    r"\bsenior\s+engineer\b",
    r"\bprincipal\s+engineer\b",
    r"\bsite\s+agent\b",
    r"\bclerk\s+of\s+works\b",
    r"\bengineering\s+inspector\b",
    r"\b(?:assistant\s+|senior\s+)?project\s+manager\b",
    r"\bconstruction\s+manager\b",
    r"\bsite\s+manager\b",
    r"\bdesign\s+manager\b",
)

EARLY_CAREER_TITLE_PATTERNS: tuple[str, ...] = (
    r"\bintern(?:ship)?\b",
    r"\bapprentice(?:ship)?\b",
    r"\bgraduate\b",
    r"\btrainee\b",
    r"\bplacement\b",
)

CLEAR_NON_CIVIL_TITLE_PATTERNS: tuple[str, ...] = (
    r"\bsoftware\s+engineer\b",
    r"\bsite\s+reliability\s+engineer\b",
    r"\bdevops\s+engineer\b",
    r"\bcloud\s+(?:infrastructure\s+)?engineer\b",
    r"\bnetwork\s+(?:infrastructure\s+)?engineer\b",
    r"\bdata\s+engineer\b",
    r"\bsecurity\s+engineer\b",
    r"\bcyber(?:security)?\s+engineer\b",
    r"\bsystems?\s+engineer\b",
    r"\belectrical\s+engineer\b",
    r"\bmechanical\s+engineer\b",
    r"\bprocess\s+engineer\b",
    r"\bchemical\s+engineer\b",
    r"\belectronics?\s+engineer\b",
    r"\bquantity\s+surveyor\b",
    r"\barchitect\b",
    r"\bbim\s+(?:coordinator|manager|technician)\b",
)

# Weighted signals intentionally omit the bare word "infrastructure", because that is
# precisely where civil and IT titles collide.
CIVIL_SIGNAL_WEIGHTS: dict[str, int] = {
    "civil engineering": 6,
    "civil engineer": 6,
    "civil works": 5,
    "discipline: civil": 6,
    "discipline civil": 6,
    "civil 3d": 6,
    "highway": 5,
    "motorway": 5,
    "road design": 5,
    "roads": 4,
    "roadworks": 4,
    "pavement": 5,
    "drainage": 5,
    "stormwater": 5,
    "wastewater": 5,
    "water network": 4,
    "sewer": 4,
    "earthworks": 5,
    "setting out": 5,
    "site supervision": 4,
    "site inspection": 4,
    "construction site": 4,
    "concrete": 3,
    "reinforced concrete": 4,
    "bridge": 4,
    "transport infrastructure": 5,
    "rail infrastructure": 5,
    "railway": 4,
    "permanent way": 6,
    "track alignment": 5,
    "geometric design": 5,
    "horizontal alignment": 5,
    "vertical alignment": 5,
    "traffic engineering": 5,
    "public realm": 4,
    "land development": 4,
    "municipal": 3,
    "utilities coordination": 4,
    "contractor supervision": 4,
    "boq": 3,
    "bill of quantities": 3,
    "autocad": 2,
    "tii": 4,
    "transport infrastructure ireland": 6,
    "nta": 3,
    "dmurs": 5,
    "nec contract": 3,
    "fidic": 3,
}

NON_CIVIL_SIGNAL_WEIGHTS: dict[str, int] = {
    "aws": 6,
    "amazon web services": 6,
    "azure": 6,
    "google cloud": 6,
    "gcp": 5,
    "kubernetes": 6,
    "terraform": 6,
    "devops": 6,
    "cloud infrastructure": 7,
    "network infrastructure": 7,
    "networking infrastructure": 7,
    "windows server": 6,
    "linux server": 5,
    "active directory": 6,
    "vmware": 6,
    "virtualization": 5,
    "cybersecurity": 6,
    "software development": 6,
    "site reliability": 7,
    "microservices": 5,
    "database": 4,
    "sql server": 4,
    "cisco": 5,
    "lan": 4,
    "wan": 4,
    "firewall": 5,
    "telecommunications": 4,
    "electrical systems": 4,
    "mechanical systems": 4,
    "manufacturing": 3,
    "process engineering": 5,
    "plc": 4,
    "scada": 3,
}

ROLE_FAMILIES: tuple[tuple[str, str, int], ...] = (
    (r"\bhighways?\s+(?:design\s+)?engineer\b", "highway_engineer", 98),
    (r"\broads?\s+(?:design\s+)?engineer\b", "roads_engineer", 97),
    (r"\btransport(?:ation)?\s+engineer\b", "transportation_engineer", 94),
    (r"\btraffic\s+engineer\b", "traffic_engineer", 88),
    (r"\bpavement\s+engineer\b", "pavement_engineer", 92),
    (r"\bassistant\s+resident\s+engineer\b", "assistant_resident_engineer", 93),
    (r"\bresident\s+engineer\b", "resident_engineer", 96),
    (r"\bcivil\s+design\s+engineer\b", "civil_design_engineer", 95),
    (r"\bcivil\s+site\s+engineer\b", "site_engineer", 95),
    (r"\bsite\s+engineer\b", "site_engineer", 92),
    (r"\bsetting\s+out\s+engineer\b", "setting_out_engineer", 90),
    (r"\bsection\s+engineer\b", "section_engineer", 88),
    (r"\bpermanent\s+way\s+engineer\b", "rail_engineer", 90),
    (r"\btrack\s+engineer\b", "rail_engineer", 88),
    (r"\brail(?:way)?\s+(?:civil\s+)?engineer\b", "rail_engineer", 88),
    (r"\bpublic\s+realm\s+engineer\b", "public_realm_engineer", 88),
    (r"\bland\s+development\s+engineer\b", "site_development_engineer", 88),
    (r"\bsite\s+development\s+engineer\b", "site_development_engineer", 88),
    (r"\bmunicipal\s+engineer\b", "civil_engineer", 86),
    (r"\bdrainage\s+engineer\b", "drainage_engineer", 86),
    (r"\bwastewater\s+engineer\b", "water_engineer", 84),
    (r"\bwater(?:\s*/\s*wastewater|\s+and\s+wastewater)?\s+engineer\b", "water_engineer", 84),
    (r"\butilities\s+engineer\b", "utilities_engineer", 82),
    (r"\bcivil\s+project\s+engineer\b", "project_engineer", 92),
    (r"\bcivil\s+engineer\b", "civil_engineer", 90),
    (r"\bcivil\s+(?:works\s+)?inspector\b", "civil_inspector", 84),
    (r"\b(?:road|roads|highway|works)\s+inspector\b", "civil_inspector", 80),
    (r"\binfrastructure\s+engineer\b", "infrastructure_engineer", 82),
    (r"\bproject\s+engineer\b", "project_engineer", 78),
    (r"\bconstruction\s+engineer\b", "construction_engineer", 80),
    (r"\bassistant\s+engineer\b", "assistant_engineer", 76),
    (r"\bdesign\s+engineer\b", "design_engineer", 72),
    (r"\bengineering\s+inspector\b", "civil_inspector", 72),
    (r"\bsite\s+agent\b", "site_agent", 80),
    (r"\bclerk\s+of\s+works\b", "clerk_of_works", 74),
    (r"\b(?:assistant\s+|senior\s+)?project\s+manager\b", "project_manager", 64),
    (r"\bconstruction\s+manager\b", "construction_manager", 64),
    (r"\bsite\s+manager\b", "site_manager", 62),
    (r"\bdesign\s+manager\b", "design_manager", 60),
    (r"\bengineer\s*/\s*senior\s+engineer\b", "engineer", 70),
    (r"\bsenior\s+engineer\b", "engineer", 68),
    (r"\bprincipal\s+engineer\b", "engineer", 66),
)


@dataclass(frozen=True)
class DomainEvidence:
    domain: str
    civil_score: int
    non_civil_score: int
    civil_terms: tuple[str, ...] = ()
    non_civil_terms: tuple[str, ...] = ()


def _matches_any(patterns: tuple[str, ...], value: str) -> bool:
    return any(re.search(pattern, value, re.I) for pattern in patterns)


def _weighted_terms(text: str, weights: dict[str, int]) -> tuple[int, tuple[str, ...]]:
    lowered = text.casefold()
    matched = tuple(term for term in weights if term in lowered)
    return sum(weights[term] for term in matched), matched


def is_early_career_title(title: str) -> bool:
    return _matches_any(EARLY_CAREER_TITLE_PATTERNS, normalize_space(title))


def is_clear_non_civil_title(title: str) -> bool:
    clean = normalize_space(title)
    if _matches_any(STRONG_CIVIL_TITLE_PATTERNS, clean):
        return False
    return _matches_any(CLEAR_NON_CIVIL_TITLE_PATTERNS, clean)


def is_plausible_target_title(title: str) -> bool:
    clean = normalize_space(title)
    if not clean or is_early_career_title(clean):
        return False
    if _matches_any(STRONG_CIVIL_TITLE_PATTERNS, clean):
        return True
    if _matches_any(AMBIGUOUS_TITLE_PATTERNS, clean):
        return True
    if is_clear_non_civil_title(clean):
        return False
    lowered = clean.casefold()
    return any(
        term in lowered
        for term in (
            "engineer",
            "engineering inspector",
            "site agent",
            "clerk of works",
            "project manager",
            "construction manager",
            "site manager",
            "design manager",
            "civil inspector",
            "works inspector",
        )
    )


def role_family_for_title(title: str) -> tuple[str, int]:
    clean = normalize_space(title)
    best_family = "other"
    best_score = 0
    for pattern, family, score in ROLE_FAMILIES:
        if re.search(pattern, clean, re.I) and score > best_score:
            best_family = family
            best_score = score
    return best_family, best_score


def classify_civil_domain(title: str, text: str) -> DomainEvidence:
    clean_title = normalize_space(title)
    combined = normalize_space(f"{title} {text}")

    civil_score, civil_terms = _weighted_terms(combined, CIVIL_SIGNAL_WEIGHTS)
    non_civil_score, non_civil_terms = _weighted_terms(combined, NON_CIVIL_SIGNAL_WEIGHTS)

    strong_civil_title = _matches_any(STRONG_CIVIL_TITLE_PATTERNS, clean_title)
    explicit_non_civil_title = is_clear_non_civil_title(clean_title)

    if explicit_non_civil_title and civil_score < 6:
        domain = NON_CIVIL
    elif strong_civil_title and non_civil_score < civil_score + 6:
        domain = CIVIL
    elif civil_score >= 6 and civil_score >= non_civil_score + 2:
        domain = CIVIL
    elif non_civil_score >= 6 and non_civil_score >= civil_score + 2:
        domain = NON_CIVIL
    else:
        domain = UNCLEAR

    return DomainEvidence(
        domain=domain,
        civil_score=civil_score,
        non_civil_score=non_civil_score,
        civil_terms=civil_terms[:8],
        non_civil_terms=non_civil_terms[:8],
    )
