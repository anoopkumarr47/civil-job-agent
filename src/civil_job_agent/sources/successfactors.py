from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import canonicalize_url, normalize_space
from ..relevance import is_plausible_target_title
from .web_boards import ConfiguredWebBoard

logger = logging.getLogger(__name__)

DEFAULT_IRELAND_TERMS = (
    "dublin",
    "cork",
    "galway",
    "limerick",
    "waterford",
    "ireland",
    ", ie",
)


class SuccessFactorsSource(ConfiguredWebBoard):
    """Paginate SAP SuccessFactors career search results and retain Irish candidates."""

    def __init__(self, config: dict, *, request_timeout: int, max_links: int) -> None:
        super().__init__(config, request_timeout=request_timeout, max_links=max_links)
        self.search_url = str(config["search_url"])
        self.page_size = max(1, int(config.get("page_size", 20)))
        self.max_pages = max(1, int(config.get("max_pages", 60)))
        self.location_terms = tuple(
            normalize_space(str(x)).casefold()
            for x in config.get("ireland_location_terms", DEFAULT_IRELAND_TERMS)
            if normalize_space(str(x))
        )

    def _page_url(self, page_index: int) -> str:
        separator = "&" if "?" in self.search_url else "?"
        offset = page_index * self.page_size
        return (
            f"{self.search_url}{separator}"
            f"sortColumn=referencedate&sortDirection=desc&startrow={offset}"
        )

    def _discover_links(self) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        for page_index in range(self.max_pages):
            url = self._page_url(page_index)
            try:
                response = self.client.request(
                    "GET",
                    url,
                    timeout=self.request_timeout,
                    attempts=2,
                )
            except Exception as exc:
                logger.warning("%s search page failed %s: %s", self.name, url, exc)
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            anchors = [
                anchor
                for anchor in soup.find_all("a", href=True)
                if "/job/" in str(anchor.get("href", "")).casefold()
            ]
            if not anchors:
                if page_index == 0:
                    logger.warning("%s search page exposed no job links", self.name)
                break

            new_on_page = 0
            for anchor in anchors:
                title = normalize_space(anchor.get_text(" "))
                if not title or not is_plausible_target_title(title):
                    continue

                row = anchor.find_parent("tr")
                context = normalize_space(row.get_text(" ") if row else title).casefold()
                if self.location_terms and not any(term in context for term in self.location_terms):
                    continue

                href = canonicalize_url(urljoin(url, str(anchor["href"])))
                if href in seen or not self._looks_like_job(href, title):
                    continue
                seen.add(href)
                found.append(href)
                new_on_page += 1
                if len(found) >= self.max_links:
                    break

            logger.info(
                "%s SuccessFactors page %s yielded %s new Irish candidate link(s)",
                self.name,
                page_index + 1,
                new_on_page,
            )
            if len(found) >= self.max_links:
                break

        logger.info(
            "%s SuccessFactors discovery yielded %s Irish candidate link(s)",
            self.name,
            len(found),
        )
        return found
