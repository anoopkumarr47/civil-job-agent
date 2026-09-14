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

    groq_api_url: str
    groq_api_key: str | None
    groq_model: str
    gemini_api_key: str | None
    gemini_model: str

    ai_timeout: int
    ai_required: bool
    ai_preflight: bool
    groq_min_interval_seconds: float
    ai_max_evidence_chars: int
    ai_max_provisional_ratio: float
    run_health_file: str

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
            max_links_per_source=_env_int("MAX_LINKS_PER_SOURCE", 160),
            groq_api_url=os.environ.get(
                "GROQ_API_URL",
                "https://api.groq.com/openai/v1/chat/completions",
            ),
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            # Do not inherit legacy AI_MODEL. Production model selection must be explicit.
            groq_model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
            gemini_api_key=os.environ.get("GEMINI_API_KEY"),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
            ai_timeout=_env_int("AI_TIMEOUT", 75),
            ai_required=_env_bool("AI_REQUIRED", False),
            ai_preflight=_env_bool("AI_PREFLIGHT", True),
            groq_min_interval_seconds=max(
                0.0,
                _env_float("GROQ_MIN_INTERVAL_SECONDS", 8.0),
            ),
            ai_max_evidence_chars=max(
                1600,
                _env_int("AI_MAX_EVIDENCE_CHARS", 3000),
            ),
            ai_max_provisional_ratio=min(
                1.0,
                max(0.0, _env_float("AI_MAX_PROVISIONAL_RATIO", 0.25)),
            ),
            run_health_file=os.environ.get("RUN_HEALTH_FILE", "run_health.json"),
            email_address=sender,
            email_password=os.environ.get("EMAIL_PASSWORD"),
            email_to=os.environ.get("EMAIL_TO") or sender,
            dry_run=_env_bool("DRY_RUN", False),
            mail_lookback_days=_env_int("MAIL_LOOKBACK_DAYS", 4),
            min_successful_sources=_env_int("MIN_SUCCESSFUL_SOURCES", 3),
            stale_days=_env_int("STALE_DAYS", 90),
        )


def load_json(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
