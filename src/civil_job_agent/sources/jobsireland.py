from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..http import USER_AGENT
from ..models import Job, normalize_space
from .base import Source

logger = logging.getLogger(__name__)

BASE_URL = "https://jobsireland.ie"
SEARCH_PATH = "/en-US/browse-jobs"
DETAIL_PATH = "/en-US/job-Details"

IRELAND_LOCATIONS = (
    "Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kilkenny", "Kildare",
    "Meath", "Wicklow", "Wexford", "Clare", "Kerry", "Mayo", "Sligo", "Donegal",
    "Louth", "Monaghan", "Cavan", "Westmeath", "Offaly", "Laois", "Tipperary",
    "Roscommon", "Leitrim", "Longford", "Carlow",
)


@dataclass(frozen=True)
class JobRef:
    job_id: str
    title_hint: str = ""

    @property
    def url(self) -> str:
        return f"{BASE_URL}{DETAIL_PATH}?id={self.job_id}"


def _jobpostings_from_jsonld(soup: BeautifulSoup) -> list[dict]:
    found: list[dict] = []
    for node in soup.select('script[type="application/ld+json"]'):
        raw = node.string or node.get_text(" ")
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                item_type = item.get("@type")
                if item_type == "JobPosting" or (
                    isinstance(item_type, list) and "JobPosting" in item_type
                ):
                    found.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
    return found


def _org_name(value: object) -> str:
    if isinstance(value, dict):
        return normalize_space(str(value.get("name", "")))
    return normalize_space(str(value or ""))


def _location_name(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(x for x in (_location_name(v) for v in value) if x)
    if isinstance(value, dict):
        address = value.get("address", value)
        if isinstance(address, dict):
            return normalize_space(
                ", ".join(
                    str(address.get(k, ""))
                    for k in ("addressLocality", "addressRegion", "addressCountry")
                    if address.get(k)
                )
            )
    return normalize_space(str(value or ""))


def _salary_text(value: object) -> str:
    if isinstance(value, dict):
        currency = value.get("currency", "EUR")
        amount = value.get("value", value)
        if isinstance(amount, dict):
            minimum = amount.get("minValue")
            maximum = amount.get("maxValue")
            unit = amount.get("unitText", "YEAR")
            if minimum or maximum:
                return normalize_space(
                    f"{currency} {minimum or ''} - {maximum or ''} {unit}"
                )
    return normalize_space(str(value or ""))


def _infer_location(text: str) -> str:
    head = normalize_space(text)[:3500]
    for place in IRELAND_LOCATIONS:
        if re.search(rf"\b{re.escape(place)}\b", head, re.I):
            return f"{place}, Ireland"
    if re.search(r"\b(?:Republic of )?Ireland\b", head, re.I):
        return "Ireland"
    return ""


def _context_salary(text: str) -> str:
    match = re.search(
        r"(?:salary|remuneration|pay)\s*[:\-]?\s*(€\s*[0-9][0-9,]*(?:\s*[-–]\s*€?\s*[0-9][0-9,]*)?(?:\s*(?:per annum|p\.?a\.?|yearly|annual))?)",
        text,
        re.I,
    )
    return normalize_space(match.group(1)) if match else ""


class JobsIrelandSource(Source):
    """Browser-first JobsIreland adapter using one Chromium session per sweep."""

    name = "JobsIreland"

    def __init__(self, config: dict, *, max_links: int) -> None:
        self.config = config
        self.search_terms = [
            normalize_space(str(value))
            for value in config.get("search_terms", [])
            if normalize_space(str(value))
        ]
        self.max_links = min(max_links, int(config.get("max_links", max_links)))
        self.page_size = max(10, min(100, int(config.get("page_size", 100))))
        self.max_pages = max(1, int(config.get("max_pages", 1)))
        self.navigation_timeout_ms = max(
            5_000, int(config.get("navigation_timeout_ms", 25_000))
        )
        self.search_budget_seconds = max(
            30, int(config.get("search_budget_seconds", 180))
        )
        self.detail_budget_seconds = max(
            30, int(config.get("detail_budget_seconds", 180))
        )
        self.settle_ms = max(250, int(config.get("settle_ms", 1_000)))

    def _search_url(self, term: str, page: int = 1) -> str:
        params = {
            "CareerlevelId": -1,
            "NaceCode": -1,
            "RemoteOrBlendedJobType": -1,
            "VacancyTypeId": -1,
            "keyWord": term,
            "page": page,
            "pageSize": self.page_size,
            "vacancyId": -1,
        }
        return f"{BASE_URL}{SEARCH_PATH}?{urlencode(params)}"

    @staticmethod
    def _job_id_from_url(url: str) -> str | None:
        parsed = urlparse(url)
        if "job-details" not in parsed.path.casefold():
            return None
        values = parse_qs(parsed.query).get("id", [])
        if not values:
            return None
        value = values[0].strip()
        return value if value.isdigit() else None

    @classmethod
    def _refs_from_anchors(cls, anchors: list[dict]) -> list[JobRef]:
        refs: list[JobRef] = []
        seen: set[str] = set()
        for item in anchors:
            if not isinstance(item, dict):
                continue
            job_id = cls._job_id_from_url(str(item.get("href", "")))
            if not job_id or job_id in seen:
                continue
            seen.add(job_id)
            refs.append(
                JobRef(
                    job_id=job_id,
                    title_hint=normalize_space(str(item.get("text", "")))[:220],
                )
            )
        return refs

    @staticmethod
    def _rendered_anchors(page) -> list[dict]:
        return page.eval_on_selector_all(
            "a[href]",
            """els => els.map(a => ({
                href: a.href,
                text: (a.innerText || a.textContent || '').trim()
            }))""",
        )

    def _navigate(self, page, url: str) -> None:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.navigation_timeout_ms,
        )
        try:
            page.wait_for_selector(
                'a[href*="job-Details?id="], a[href*="job-details?id="]',
                timeout=min(6_000, self.navigation_timeout_ms),
            )
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(self.settle_ms)
        for _ in range(2):
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(300)

    def _discover_refs(self, page) -> list[JobRef]:
        found: dict[str, JobRef] = {}
        deadline = time.monotonic() + self.search_budget_seconds

        for term in self.search_terms:
            if time.monotonic() >= deadline or len(found) >= self.max_links:
                break
            term_new = 0
            for page_number in range(1, self.max_pages + 1):
                if time.monotonic() >= deadline or len(found) >= self.max_links:
                    break
                url = self._search_url(term, page_number)
                try:
                    self._navigate(page, url)
                    refs = self._refs_from_anchors(self._rendered_anchors(page))
                except Exception as exc:
                    logger.warning(
                        "%s search failed term=%r page=%s: %s",
                        self.name,
                        term,
                        page_number,
                        exc,
                    )
                    break

                new_on_page = 0
                for ref in refs:
                    if ref.job_id not in found:
                        found[ref.job_id] = ref
                        term_new += 1
                        new_on_page += 1
                        if len(found) >= self.max_links:
                            break

                logger.info(
                    "%s search term=%r page=%s yielded %s ref(s), %s new",
                    self.name,
                    term,
                    page_number,
                    len(refs),
                    new_on_page,
                )
                if not refs or new_on_page == 0:
                    break

            logger.info(
                "%s search term=%r contributed %s unique vacancy ID(s)",
                self.name,
                term,
                term_new,
            )

        logger.info(
            "%s discovered %s unique vacancy ID(s) across %s search term(s)",
            self.name,
            len(found),
            len(self.search_terms),
        )
        return list(found.values())

    @staticmethod
    def _parse_detail_html(html: str, ref: JobRef) -> Job | None:
        soup = BeautifulSoup(html, "html.parser")
        structured = _jobpostings_from_jsonld(soup)

        if structured:
            item = structured[0]
            title = normalize_space(str(item.get("title", ""))) or ref.title_hint
            company = _org_name(item.get("hiringOrganization"))
            location = _location_name(item.get("jobLocation"))
            description = normalize_space(
                BeautifulSoup(
                    str(item.get("description", "")),
                    "html.parser",
                ).get_text(" ")
            )
            salary = _salary_text(item.get("baseSalary"))
            posted = normalize_space(str(item.get("datePosted", "")))
        else:
            title_node = (
                soup.select_one("h1")
                or soup.select_one('[property="og:title"]')
                or soup.select_one("h2")
            )
            if title_node and title_node.name == "meta":
                title = normalize_space(str(title_node.get("content", "")))
            else:
                title = normalize_space(
                    title_node.get_text(" ") if title_node else ""
                )
            title = title or ref.title_hint

            company = ""
            for selector in (
                '[class*="company"]',
                '[class*="employer"]',
                '[data-testid*="company"]',
            ):
                node = soup.select_one(selector)
                if node:
                    company = normalize_space(node.get_text(" "))[:180]
                    if company:
                        break

            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            description = normalize_space(soup.get_text(" "))
            location = _infer_location(description)
            salary = _context_salary(description)
            posted = ""

        if not title or len(description) < 100:
            return None

        return Job(
            source="JobsIreland",
            url=ref.url,
            title=title[:220],
            company=company[:180],
            location=(location or "Ireland")[:180],
            text=description[:30000],
            salary_text=salary[:220],
            posted_text=posted[:120],
        )

    def _parse_details(self, page, refs: list[JobRef]) -> list[Job]:
        jobs: list[Job] = []
        deadline = time.monotonic() + self.detail_budget_seconds

        for index, ref in enumerate(refs, start=1):
            if time.monotonic() >= deadline:
                logger.warning(
                    "%s detail budget reached after %s/%s vacancies; continuing with collected jobs",
                    self.name,
                    index - 1,
                    len(refs),
                )
                break
            try:
                page.goto(
                    ref.url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )
                page.wait_for_timeout(self.settle_ms)
                job = self._parse_detail_html(page.content(), ref)
                if job:
                    jobs.append(job)
            except Exception as exc:
                logger.warning(
                    "%s detail failed id=%s: %s",
                    self.name,
                    ref.job_id,
                    exc,
                )

        logger.info(
            "%s parsed %s relevant detail page(s) from %s unique vacancy ID(s)",
            self.name,
            len(jobs),
            len(refs),
        )
        return jobs

    def discover(self) -> list[Job]:
        if not self.search_terms:
            logger.warning("%s has no configured search terms", self.name)
            return []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=USER_AGENT,
                locale="en-IE",
                viewport={"width": 1440, "height": 1000},
            )
            search_page = context.new_page()
            detail_page = context.new_page()
            try:
                refs = self._discover_refs(search_page)
                return self._parse_details(detail_page, refs)
            finally:
                context.close()
                browser.close()
