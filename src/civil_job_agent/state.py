from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Assessment, Job


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    VERSION = 2

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.data = {"version": self.VERSION, "updated_at": None, "jobs": {}}
        self.dirty = False

    def load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("version") != self.VERSION or not isinstance(raw.get("jobs"), dict):
            raise RuntimeError("Unsupported or corrupt state version")
        self.data = raw
        self.dirty = False

    def needs_review(self, job: Job, profile_version: str, policy_version: str, ai_available: bool) -> bool:
        record = self.data["jobs"].get(job.identity_key)
        if not record:
            return True
        if record.get("content_hash") != job.content_hash:
            return True
        if record.get("profile_version") != profile_version or record.get("policy_version") != policy_version:
            return True
        raw = record.get("assessment")
        if not isinstance(raw, dict):
            return True
        return Assessment.from_dict(raw).provisional and ai_available

    def record(self, job: Job, assessment: Assessment, profile_version: str, policy_version: str) -> None:
        previous = self.data["jobs"].get(job.identity_key, {})
        self.data["jobs"][job.identity_key] = {
            "identity_key": job.identity_key,
            "url": job.canonical_url,
            "source": job.source,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "content_hash": job.content_hash,
            "profile_version": profile_version,
            "policy_version": policy_version,
            "assessment": assessment.to_dict(),
            "first_seen": previous.get("first_seen") or now(),
            "last_seen": now(),
            "notified_hash": previous.get("notified_hash"),
            "notified_at": previous.get("notified_at"),
        }
        self.dirty = True

    def touch(self, job: Job) -> None:
        record = self.data["jobs"].get(job.identity_key)
        if not record:
            return
        today = now()[:10]
        if str(record.get("last_seen", ""))[:10] != today:
            record["last_seen"] = now()
            self.dirty = True

    def assessment_for(self, job: Job, profile_version: str, policy_version: str) -> Assessment | None:
        record = self.data["jobs"].get(job.identity_key)
        if not record:
            return None
        if record.get("content_hash") != job.content_hash:
            return None
        if record.get("profile_version") != profile_version or record.get("policy_version") != policy_version:
            return None
        raw = record.get("assessment")
        return Assessment.from_dict(raw) if isinstance(raw, dict) else None

    def is_notified(self, job: Job) -> bool:
        record = self.data["jobs"].get(job.identity_key, {})
        return record.get("notified_hash") == job.content_hash

    def mark_notified(self, job: Job) -> None:
        record = self.data["jobs"][job.identity_key]
        record["notified_hash"] = job.content_hash
        record["notified_at"] = now()
        self.dirty = True

    def prune(self, stale_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        removed = 0
        for key, record in list(self.data["jobs"].items()):
            value = record.get("last_seen")
            try:
                seen = datetime.fromisoformat(str(value))
            except Exception:
                continue
            if seen < cutoff:
                del self.data["jobs"][key]
                removed += 1
        if removed:
            self.dirty = True
        return removed

    def save(self) -> bool:
        if not self.dirty:
            return False
        self.data["updated_at"] = now()
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        self.dirty = False
        return True
