from __future__ import annotations

import hashlib
import html
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import Settings
from .models import Assessment, Job


def _sorted(items: list[tuple[Job, Assessment]]) -> list[tuple[Job, Assessment]]:
    return sorted(items, key=lambda item: (-item[1].score, item[0].title.casefold(), item[0].company.casefold()))


def _message_id(items: list[tuple[Job, Assessment]], sender: str) -> str:
    material = "|".join(f"{job.identity_key}:{job.content_hash}" for job, _ in _sorted(items))
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    domain = sender.split("@", 1)[1] if "@" in sender else "civil-job-agent.local"
    return f"<civil-job-agent-{digest}@{domain}>"


def send_email(items: list[tuple[Job, Assessment]], settings: Settings) -> None:
    if not items:
        return
    if not settings.email_address or not settings.email_password or not settings.email_to:
        raise RuntimeError("EMAIL_ADDRESS, EMAIL_PASSWORD and EMAIL_TO are required")

    items = _sorted(items)
    subject = f"Ireland Civil Jobs: {len(items)} new high-fit role{'s' if len(items) != 1 else ''}"
    plain = ["Ranked Ireland civil-engineering opportunities for an India-based applicant:", ""]
    blocks: list[str] = []
    for job, a in items:
        plain.extend(
            [
                f"{a.score}/100 — {job.title}",
                f"Company: {job.company or 'Not stated'}",
                f"Location: {job.location or 'Ireland'}",
                f"Source: {job.source}",
                f"Salary: {job.salary_text or 'Not stated'}",
                f"Permit: {a.permit_path} | Relocation fit: {a.relocation_fit}",
                f"Why: {a.reason}",
                f"Strengths: {', '.join(a.strengths) or '—'}",
                f"Gaps: {', '.join(a.gaps) or '—'}",
                job.url,
                "",
            ]
        )
        blocks.append(
            f"""
            <section style="padding:18px 0;border-bottom:1px solid #e5e7eb">
              <div style="font-size:13px;color:#64748b"><strong>{a.score}/100</strong> · {html.escape(a.role_family)} · {html.escape(a.permit_path)}</div>
              <h3 style="margin:6px 0;color:#0f172a">{html.escape(job.title)}</h3>
              <div>{html.escape(job.company or 'Not stated')} · {html.escape(job.location or 'Ireland')}</div>
              <div style="font-size:13px;color:#64748b">Source: {html.escape(job.source)} · Salary: {html.escape(job.salary_text or 'Not stated')}</div>
              <p>{html.escape(a.reason)}</p>
              <p><strong>Strengths:</strong> {html.escape(', '.join(a.strengths) or '—')}</p>
              <p><strong>Check:</strong> {html.escape(', '.join(a.gaps) or '—')}</p>
              <a href="{html.escape(job.url, quote=True)}">Open job</a>
            </section>
            """
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Ireland Civil Job Agent <{settings.email_address}>"
    msg["To"] = settings.email_to
    msg["Subject"] = subject
    msg["Message-ID"] = _message_id(items, settings.email_address)
    msg.attach(MIMEText("\n".join(plain), "plain", "utf-8"))
    msg.attach(MIMEText("<html><body><h2>Best new Ireland civil-engineering matches</h2>" + "".join(blocks) + "</body></html>", "html", "utf-8"))

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(settings.email_address, settings.email_password)
                server.send_message(msg)
            return
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt + 1)
    raise RuntimeError(f"SMTP failed after 3 attempts: {last_error}")
