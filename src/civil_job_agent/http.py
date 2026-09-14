from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)
RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class HttpClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-IE,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            }
        )

    def request(
        self,
        method: str,
        url: str,
        *,
        timeout: int,
        attempts: int = 3,
        **kwargs: Any,
    ) -> requests.Response:
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                if response.status_code in RETRYABLE and attempt < attempts - 1:
                    retry_after = response.headers.get("Retry-After")
                    delay = min(60.0, 2**attempt + random.uniform(0.2, 1.5))
                    if retry_after:
                        try:
                            delay = min(90.0, float(retry_after))
                        except ValueError:
                            pass
                    logger.warning("HTTP %s from %s; retrying in %.1fs", response.status_code, url, delay)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last = exc
                if isinstance(exc, requests.HTTPError):
                    raise
                if attempt < attempts - 1:
                    time.sleep(min(30.0, 2**attempt + random.uniform(0.2, 1.5)))
                    continue
                raise
        if last:
            raise last
        raise RuntimeError(f"Request failed: {url}")
