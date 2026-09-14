from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import canonicalize_url, normalize_space
from ..relevance import is_plausible_target_title
from .web_boards import ConfiguredWebBoard

logger = logging.getLogger(__name__)


class OleeoSource(ConfiguredWebBoard):
    """Discover and paginate Oleeo/TAL job boards from a stable employer landing page."""

    def __init__(self, config: dict, *, request_timeout: int, max_links: int) -> None:
        super().__init__(config, request_timeout=request_timeout, max_links=max_links)
        self.landing_url = str(config["landing_url"])
        self.board_host = str(config["board_host"]).casefold()
        self.max_pages = max(1, int(config.get("max_pages", 30)))

    def _board_url(self) -> str:
        response = self.client.request(
            "GET",
            self.landing_url,
            timeout=self.request_timeout,
            attempts=2,
        )
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = urljoin(self.landing_url, str(anchor["href"]))
            text = normalize_space(anchor.get_text(" ")).casefold()
            if self.board_host in href.casefold() and "job search" in text:
                return href
        raise RuntimeError(f"{self.name} landing page did not expose the Oleeo job-search link")

    def _discover_links(self) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        page_url = self._board_url()

        for page_number in range(1, self.max_pages + 1):
            response = self.client.request(
                "GET",
                page_url,
                timeout=self.request_timeout,
                attempts=2,
            )
            soup = BeautifulSoup(response.text, "html.parser")

            new_on_page = 0
            for anchor in soup.find_all("a", href=True):
                title = normalize_space(anchor.get_text(" "))
                if not title or not is_plausible_target_title(title):
                    continue
                href = canonicalize_url(urljoin(page_url, str(anchor["href"])))
                if href in seen or not self._looks_like_job(href, title):
                    continue
                seen.add(href)
                found.append(href)
                new_on_page += 1
                if len(found) >= self.max_links:
                    break

            logger.info(
                "%s Oleeo page %s yielded %s new candidate link(s)",
                self.name,
                page_number,
                new_on_page,
            )
            if len(found) >= self.max_links:
                break

            next_url = ""
            for anchor in soup.find_all("a", href=True):
                text = normalize_space(anchor.get_text(" ")).casefold()
                if "next page" in text:
                    next_url = urljoin(page_url, str(anchor["href"]))
                    break
            if not next_url or canonicalize_url(next_url) == canonicalize_url(page_url):
                break
            page_url = next_url

        logger.info("%s Oleeo discovery yielded %s candidate link(s)", self.name, len(found))
        return found
