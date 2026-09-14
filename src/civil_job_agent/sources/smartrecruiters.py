from __future__ import annotations

import logging
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import HttpClient
from ..models import Job, normalize_space
from .base import Source

logger = logging.getLogger(__name__)

TARGET_TERMS = (
    "civil",
    "highway",
    "road",
    "transport",
    "resident engineer",
    "site engineer",
    "project engineer",
    "infrastructure",
    "setting out",
    "rail",
    "water",
)


def _html_text(value: object) -> str:
    if not value:
        return ""
    return normalize_space(BeautifulSoup(str(value), "html.parser").get_text(" "))


class SmartRecruitersCompanySource(Source):
    """Use SmartRecruiters' public Posting API rather than scraping its career UI."""

    def __init__(self, config: dict, *, request_timeout: int, max_links: int) -> None:
        self.config = config
        self.name = str(config["name"])
        self.company_identifier = str(config["company_identifier"])
        self.request_timeout = request_timeout
        self.max_links = min(max_links, int(config.get("max_links", max_links)))
        self.client = HttpClient()

    def _list_url(self, offset: int) -> str:
        params = {
            "limit": 100,
            "offset": offset,
            "country": self.config.get("country", "ie"),
            "destination": "PUBLIC",
        }
        return (
            f"https://api.smartrecruiters.com/v1/companies/{self.company_identifier}/postings?"
            + urlencode(params)
        )

    def _target_title(self, title: str) -> bool:
        lowered = title.casefold()
        return any(term in lowered for term in TARGET_TERMS)

    def _detail_to_job(self, item: dict, detail: dict) -> Job | None:
        title = normalize_space(str(detail.get("name") or item.get("name") or ""))
        if not title or not self._target_title(title):
            return None

        location_data = detail.get("location") or item.get("location") or {}
        if not isinstance(location_data, dict):
            location_data = {}
        country = normalize_space(str(location_data.get("country") or ""))
        city = normalize_space(str(location_data.get("city") or ""))
        region = normalize_space(str(location_data.get("region") or ""))
        location = ", ".join(x for x in [city, region, country] if x) or "Ireland"
        if country and country.casefold() not in {"ie", "irl", "ireland"} and "ireland" not in country.casefold():
            return None

        company_data = detail.get("company") or item.get("company") or {}
        company = (
            normalize_space(str(company_data.get("name") or self.name))
            if isinstance(company_data, dict)
            else self.name
        )

        job_ad = detail.get("jobAd") or {}
        parts: list[str] = []
        if isinstance(job_ad, dict):
            for key in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
                text = _html_text(job_ad.get(key))
                if text:
                    parts.append(text)
            sections = job_ad.get("sections")
            if isinstance(sections, dict):
                for section in sections.values():
                    if isinstance(section, dict):
                        title_text = normalize_space(str(section.get("title") or ""))
                        body = _html_text(section.get("text"))
                        if title_text or body:
                            parts.append(f"{title_text} {body}".strip())

        description = normalize_space(" ".join(parts))
        if len(description) < 80:
            return None

        compensation = detail.get("compensation")
        salary = ""
        if isinstance(compensation, dict):
            minimum = compensation.get("min")
            maximum = compensation.get("max")
            currency = compensation.get("currency") or "EUR"
            period = compensation.get("period") or ""
            if minimum or maximum:
                salary = normalize_space(f"{currency} {minimum or ''} - {maximum or ''} {period}")

        posting_id = str(detail.get("id") or item.get("id") or "")
        public_url = normalize_space(str(detail.get("applyUrl") or ""))
        if not public_url and posting_id:
            public_url = f"https://jobs.smartrecruiters.com/{self.company_identifier}/{posting_id}"
        if not public_url:
            return None

        return Job(
            source=self.name,
            url=public_url,
            title=title[:220],
            company=company[:180],
            location=location[:180],
            text=description[:30000],
            salary_text=salary[:220],
            posted_text=normalize_space(str(detail.get("releasedDate") or item.get("releasedDate") or ""))[:120],
        )

    def discover(self) -> list[Job]:
        jobs: list[Job] = []
        offset = 0
        seen_ids: set[str] = set()

        while len(seen_ids) < self.max_links:
            response = self.client.request("GET", self._list_url(offset), timeout=self.request_timeout)
            payload = response.json()
            content = payload.get("content") or []
            if not isinstance(content, list) or not content:
                break

            for item in content:
                if not isinstance(item, dict):
                    continue
                posting_id = str(item.get("id") or item.get("uuid") or "")
                if not posting_id or posting_id in seen_ids:
                    continue
                seen_ids.add(posting_id)
                if not self._target_title(normalize_space(str(item.get("name") or ""))):
                    continue

                detail_url = item.get("ref") or (
                    f"https://api.smartrecruiters.com/v1/companies/{self.company_identifier}/postings/{posting_id}"
                )
                try:
                    detail = self.client.request("GET", str(detail_url), timeout=self.request_timeout).json()
                    if isinstance(detail, dict):
                        job = self._detail_to_job(item, detail)
                        if job:
                            jobs.append(job)
                except Exception as exc:
                    logger.warning("%s detail fetch failed for %s: %s", self.name, posting_id, exc)

                if len(seen_ids) >= self.max_links:
                    break

            total = int(payload.get("totalFound") or 0)
            offset += int(payload.get("limit") or 100)
            if offset >= total or offset <= 0:
                break

        logger.info("%s SmartRecruiters API yielded %s relevant job(s)", self.name, len(jobs))
        return jobs
