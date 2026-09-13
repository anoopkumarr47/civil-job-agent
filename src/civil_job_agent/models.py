from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in {"trk", "trackingid", "refid"}]
    )
    return urlunparse((parsed.scheme or "https", parsed.netloc.lower(), parsed.path.rstrip("/"), "", query, ""))


@dataclass(frozen=True)
class Job:
    source: str
    url: str
    title: str
    company: str
    location: str
    text: str
    salary_text: str = ""
    posted_text: str = ""

    @property
    def canonical_url(self) -> str:
        return canonicalize_url(self.url)

    @property
    def content_hash(self) -> str:
        material = "\n".join(
            [self.title, self.company, self.location, self.text, self.salary_text, self.posted_text]
        ).encode("utf-8", "ignore")
        return sha256(material).hexdigest()

    @property
    def identity_key(self) -> str:
        title = normalize_space(self.title).casefold()
        company = normalize_space(self.company).casefold()
        location = normalize_space(self.location).casefold()
        if company:
            material = f"{title}|{company}|{location}".encode("utf-8", "ignore")
        else:
            material = self.canonical_url.encode("utf-8", "ignore")
        return sha256(material).hexdigest()


@dataclass
class Assessment:
    matched: bool
    score: int
    role_family: str
    permit_path: str
    relocation_fit: str
    reason: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    hard_reject: bool = False
    source: str = "deterministic"
    provisional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Assessment":
        return cls(
            matched=bool(data.get("matched", False)),
            score=int(data.get("score", 0)),
            role_family=str(data.get("role_family", "other")),
            permit_path=str(data.get("permit_path", "unclear")),
            relocation_fit=str(data.get("relocation_fit", "low")),
            reason=str(data.get("reason", "")),
            strengths=[str(x) for x in data.get("strengths", [])],
            gaps=[str(x) for x in data.get("gaps", [])],
            hard_reject=bool(data.get("hard_reject", False)),
            source=str(data.get("source", "state")),
            provisional=bool(data.get("provisional", False)),
        )


@dataclass(frozen=True)
class SourceReport:
    name: str
    jobs: int
    ok: bool
    error: str = ""
