from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Settings:
    state_file: str
    profile_file: str
    sources_file: str
    request_timeout: int
    max_links_per_source: int
    ai_api_url: str
    ai_api_key: str | None
    ai_model: str
    ai_escalation_model: str
    ai_timeout: int
    ai_required: bool
    ai_min_interval_seconds: float
    ai_token_reserve: int
    ai_max_evidence_chars: int
    email_address: str | None
    email_password: str | None
    email_to: str | None
    dry_run: bool
    mail_lookback_days: int
    min_successful_sources: int
    stale_days: int

    @classmethod
    def from_env(cls) -> "Settings":
        sender = os.environ.get("EMAIL_ADDRESS")
        return cls(
            state_file=os.environ.get("STATE_FILE", "job_state.json"),
            profile_file=os.environ.get("PROFILE_FILE", "config/candidate_profile.json"),
            sources_file=os.environ.get("SOURCES_FILE", "config/sources.json"),
            request_timeout=_env_int("REQUEST_TIMEOUT", 25),
            max_links_per_source=_env_int("MAX_LINKS_PER_SOURCE", 120),
            ai_api_url=os.environ.get("AI_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
            ai_api_key=os.environ.get("AI_API_KEY") or os.environ.get("GROQ_API_KEY"),
            ai_model=os.environ.get("AI_PRIMARY_MODEL", "openai/gpt-oss-20b"),
            ai_escalation_model=(
                os.environ.get("AI_ESCALATION_MODEL")
                or os.environ.get("AI_MODEL")
                or "openai/gpt-oss-120b"
            ),
            ai_timeout=_env_int("AI_TIMEOUT", 90),
            ai_required=_env_bool("AI_REQUIRED", False),
            ai_min_interval_seconds=max(0.0, _env_float("AI_MIN_INTERVAL_SECONDS", 4.0)),
            ai_token_reserve=max(0, _env_int("AI_TOKEN_RESERVE", 2400)),
            ai_max_evidence_chars=max(1200, _env_int("AI_MAX_EVIDENCE_CHARS", 3600)),
            email_address=sender,
            email_password=os.environ.get("EMAIL_PASSWORD"),
            email_to=os.environ.get("EMAIL_TO") or sender,
            dry_run=_env_bool("DRY_RUN", False),
            mail_lookback_days=_env_int("MAIL_LOOKBACK_DAYS", 3),
            min_successful_sources=_env_int("MIN_SUCCESSFUL_SOURCES", 2),
            stale_days=_env_int("STALE_DAYS", 90),
        )


def load_json(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
