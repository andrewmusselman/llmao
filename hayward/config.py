"""Configuration for the Hayward gateway.

Everything is environment-driven so the same image runs locally, in CI, and
in production. Defaults are chosen so that `python -m hayward.app` works on a
laptop with no external services: dev-stub auth and a mock LLM backend.

Set HAYWARD_AUTH_MODE=asf and HAYWARD_LITELLM_MODE=proxy in production.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # --- Auth -------------------------------------------------------------
    # "dev" -> dev-stub login (no external calls; pick a uid + projects).
    # "asf" -> real asfquart OAuth (oauth.apache.org) + LDAP.
    auth_mode: str = field(default_factory=lambda: os.getenv("HAYWARD_AUTH_MODE", "dev"))

    # Site admins (uids) always allowed, may view all projects' activity.
    site_admins: List[str] = field(default_factory=lambda: _list("HAYWARD_SITE_ADMINS", []))

    # Secret for signing the asfquart/quart session cookie.
    app_secret: str = field(default_factory=lambda: os.getenv("HAYWARD_APP_SECRET", "dev-insecure-secret-change-me"))

    # --- litellm backend --------------------------------------------------
    # "mock"  -> in-process fake completion (no network; good for demos/CI).
    # "proxy" -> talk to a real litellm proxy over HTTP (production).
    litellm_mode: str = field(default_factory=lambda: os.getenv("HAYWARD_LITELLM_MODE", "mock"))

    # Base URL of the litellm proxy (when litellm_mode == "proxy").
    litellm_base_url: str = field(default_factory=lambda: os.getenv("HAYWARD_LITELLM_BASE_URL", "http://localhost:4000"))

    # The litellm proxy *master* key, used by the seam to provision teams and
    # mint per-team keys via the proxy's /team and /key admin endpoints.
    litellm_master_key: str = field(default_factory=lambda: os.getenv("HAYWARD_LITELLM_MASTER_KEY", "sk-hayward-master-dev"))

    # How long (seconds) to wait for a chat completion from the proxy. Local
    # models on modest GPUs (or reasoning models that think first) can be slow,
    # so this is generous by default and overridable.
    request_timeout_s: int = field(default_factory=lambda: int(os.getenv("HAYWARD_REQUEST_TIMEOUT_S", "600")))

    # --- Budgets ----------------------------------------------------------
    # Default monthly budget (USD) granted to a PMC team on first provision.
    default_team_budget_usd: float = field(default_factory=lambda: float(os.getenv("HAYWARD_DEFAULT_TEAM_BUDGET_USD", "100")))
    budget_duration: str = field(default_factory=lambda: os.getenv("HAYWARD_BUDGET_DURATION", "30d"))

    # --- Storage ----------------------------------------------------------
    # Where the seam persists its ASF-project -> litellm-team mapping and the
    # mock backend keeps usage. A JSON file keeps Phase 1 dependency-free;
    # swap for a real DB later without touching callers.
    state_path: str = field(default_factory=lambda: os.getenv("HAYWARD_STATE_PATH", "./hayward-state.json"))

    # --- Uploads ----------------------------------------------------------
    max_upload_bytes: int = field(default_factory=lambda: int(os.getenv("HAYWARD_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))))

    host: str = field(default_factory=lambda: os.getenv("HAYWARD_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("HAYWARD_PORT", "8080")))

    @property
    def is_dev_auth(self) -> bool:
        return self.auth_mode != "asf"

    @property
    def is_mock_llm(self) -> bool:
        return self.litellm_mode != "proxy"


settings = Settings()