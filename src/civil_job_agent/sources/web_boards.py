from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..http import USER_AGENT, HttpClient
from ..models import Job, canonicalize_url, normalize_space
from .base import Source

logger = logging.getLogger(__name__)


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
                if item_type == "JobPosting" or (isinstance(item_type, list) and "JobPosting" in item_type):
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
                return normalize_space(f"{currency} {minimum or ''} - {maximum or ''} {unit}")
    return normalize_space(str(value or ""))


class ConfiguredWebBoard(Source):
    def __init__(self, config: dict, *, request_timeout: int, max_links: int) -> None:
        self.config = config
        self.name = str(config["name"])
        self.request_timeout = request_timeout
        self.max_links = min(max_links, int(config.get("max_links", max_links)))
        self.client = HttpClient()

    def _allowed_host(self, href: str) -> bool:
        host = urlparse(href).netloc.lower()
        allowed = [str(x).lower() for x in self.config.get("allowed_hosts", [])]
        return not allowed or any(host == x or host.endswith("." + x) for x in allowed)

    def _looks_like_job(self, href: str, label: str = "") -> bool:
        if not self._allowed_host(href):
            return False
        candidate = f"{href} {label}".lower()
        excludes = [str(x).lower() for x in self.config.get("exclude_link_patterns", [])]
        if any(x in candidate for x in excludes):
            return False
        patterns = [str(x).lower() for x in self.config.get("job_link_patterns", [])]
        return any(pattern in candidate for pattern in patterns) if patterns else True

    def _discover_links(self) -> list[str]:
        found: list[str] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT, locale="en-IE", viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            try:
                for search_url in self.config.get("search_urls", []):
                    try:
                        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                        try:
                            page.wait_for_load_state("networkidle", timeout=12000)
                        except PlaywrightTimeoutError:
                            page.wait_for_timeout(2500)
                        for _ in range(3):
                            page.mouse.wheel(0, 2500)
                            page.wait_for_timeout(500)
                        anchors = page.eval_on_selector_all(
                            "a[href]",
                            "els => els.map(a => ({href: a.href, text: (a.innerText || a.textContent || '').trim()}))",
                        )
                        for item in anchors:
                            if not isinstance(item, dict):
                                continue
                            href = canonicalize_url(str(item.get("href", "")))
                            label = normalize_space(str(item.get("text", "")))
                            if href and self._looks_like_job(href, label) and href not in found:
                                found.append(href)
                                if len(found) >= self.max_links:
                                    return found
                    except Exception as exc:
                        logger.warning("%s search page failed %s: %s", self.name, search_url, exc)
            finally:
                context.close()
                browser.close()
        return found

    def _parse_detail(self, url: str) -> Job | None:
        try:
            response = self.client.request("GET", url, timeout=self.request_timeout)
        except Exception as exc:
            logger.warning("%s detail fetch failed %s: %s", self.name, url, exc)
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        structured = _jobpostings_from_jsonld(soup)
        if structured:
            item = structured[0]
            title = normalize_space(str(item.get("title", "")))
            company = _org_name(item.get("hiringOrganization"))
            location = _location_name(item.get("jobLocation")) or normalize_space(str(item.get("jobLocationType", "")))
            description = BeautifulSoup(str(item.get("description", "")), "html.parser").get_text(" ")
            description = normalize_space(description)
            salary = _salary_text(item.get("baseSalary"))
            posted = normalize_space(str(item.get("datePosted", "")))
        else:
            title_node = soup.select_one("h1") or soup.select_one('[property="og:title"]') or soup.select_one("h2")
            if title_node and title_node.name == "meta":
                title = normalize_space(str(title_node.get("content", "")))
            else:
                title = normalize_space(title_node.get_text(" ") if title_node else "")
            company = ""
            location = ""
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            description = normalize_space(soup.get_text(" "))
            salary = ""
            posted = ""
        if len(description) < 100 or not title:
            return None
        required_terms = [str(x).casefold() for x in self.config.get("required_any_terms", [])]
        haystack = f"{title} {description[:4000]}".casefold()
        if required_terms and not any(term in haystack for term in required_terms):
            return None
        return Job(
            self.name,
            canonicalize_url(url),
            title[:220],
            company[:180],
            location[:180] or "Ireland",
            description[:30000],
            salary[:220],
            posted[:120],
        )

    def discover(self) -> list[Job]:
        jobs: list[Job] = []
        links = self._discover_links()
        logger.info("%s discovered %s candidate links", self.name, len(links))
        for url in links:
            job = self._parse_detail(url)
            if job:
                jobs.append(job)
        logger.info("%s parsed %s relevant job(s)", self.name, len(jobs))
        return jobs
