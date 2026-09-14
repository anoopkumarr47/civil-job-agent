from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from ..models import Job, canonicalize_url, normalize_space
from .base import Source

logger = logging.getLogger(__name__)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


ROLE_PATTERNS = (
    r"\b(?:senior\s+|principal\s+|assistant\s+)?highways?\s+(?:design\s+)?engineer\b",
    r"\b(?:senior\s+|principal\s+|assistant\s+)?roads?\s+(?:design\s+)?engineer\b",
    r"\b(?:senior\s+|principal\s+|assistant\s+)?civil\s+(?:design\s+|site\s+|project\s+|infrastructure\s+)?engineer\b",
    r"\b(?:senior\s+|principal\s+|assistant\s+)?resident\s+engineer\b",
    r"\b(?:senior\s+|principal\s+|assistant\s+)?site\s+engineer\b",
    r"\b(?:senior\s+|principal\s+|assistant\s+)?project\s+engineer\b",
    r"\b(?:senior\s+|principal\s+)?transport(?:ation)?\s+engineer\b",
    r"\bsetting\s+out\s+engineer\b",
    r"\binfrastructure\s+engineer\b",
)


def _title_from_alert(label: str, context: str) -> str:
    import re
    clean_label = normalize_space(label)
    if any(term in clean_label.casefold() for term in ["engineer", "engineering", "highway", "roads", "resident"]):
        return clean_label[:220]
    for pattern in ROLE_PATTERNS:
        match = re.search(pattern, context, re.I)
        if match:
            return normalize_space(match.group(0))[:220]
    return clean_label[:220]


def _unwrap(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("url", "u", "target", "dest", "redirect"):
        values = query.get(key)
        if values and values[0].startswith("http"):
            return unquote(values[0])
    return url


class GmailJobAlertSource(Source):
    """Reads LinkedIn/Indeed job-alert emails using the same Gmail App Password as SMTP."""

    def __init__(
        self,
        *,
        name: str,
        address: str,
        password: str,
        allowed_hosts: list[str],
        sender_contains: list[str],
        lookback_days: int,
    ) -> None:
        self.name = name
        self.address = address
        self.password = password
        self.allowed_hosts = [x.lower() for x in allowed_hosts]
        self.sender_contains = [x.lower() for x in sender_contains]
        self.lookback_days = max(1, lookback_days)

    def _allowed(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(host == x or host.endswith("." + x) for x in self.allowed_hosts)

    def discover(self) -> list[Job]:
        results: list[Job] = []
        since = (datetime.utcnow() - timedelta(days=self.lookback_days)).strftime("%d-%b-%Y")
        with imaplib.IMAP4_SSL("imap.gmail.com", 993) as client:
            client.login(self.address, self.password)
            client.select("INBOX", readonly=True)
            status, data = client.search(None, "SINCE", since)
            if status != "OK" or not data:
                return results
            for msg_id in data[0].split()[-200:]:
                status, payload = client.fetch(msg_id, "(RFC822)")
                if status != "OK" or not payload or not isinstance(payload[0], tuple):
                    continue
                msg = email.message_from_bytes(payload[0][1])
                sender = _decode(msg.get("From")).lower()
                if self.sender_contains and not any(x in sender for x in self.sender_contains):
                    continue
                subject = _decode(msg.get("Subject"))
                html_parts: list[str] = []
                text_parts: list[str] = []
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    ctype = part.get_content_type()
                    if ctype not in {"text/html", "text/plain"}:
                        continue
                    raw = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    decoded = raw.decode(charset, "ignore")
                    (html_parts if ctype == "text/html" else text_parts).append(decoded)
                body = "\n".join(html_parts or text_parts)
                soup = BeautifulSoup(body, "html.parser")
                seen: set[str] = set()
                for anchor in soup.find_all("a", href=True):
                    url = canonicalize_url(_unwrap(str(anchor["href"])))
                    if not self._allowed(url) or url in seen:
                        continue
                    seen.add(url)
                    label = normalize_space(anchor.get_text(" "))
                    context_node = anchor.parent.parent if anchor.parent and anchor.parent.parent else anchor.parent
                    context = normalize_space(context_node.get_text(" ") if context_node else label)
                    title = _title_from_alert(label, context)
                    if not title or len(title) < 3:
                        continue
                    if not any(term in f"{title} {context}".casefold() for term in ["civil", "engineer", "highway", "road", "resident", "transport", "infrastructure", "site"]):
                        continue
                    results.append(
                        Job(
                            self.name,
                            url,
                            title,
                            "",
                            "Ireland",
                            normalize_space(f"Email subject: {subject}. Alert context: {context}")[:6000],
                        )
                    )
        logger.info("%s email alerts yielded %s candidate job link(s)", self.name, len(results))
        return results
