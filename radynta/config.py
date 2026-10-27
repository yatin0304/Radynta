"""Configuration loaded from environment variables (optionally via a .env file).

Secrets are never hard-coded. In production a missing secret key is a hard error.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments. Existing env vars win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}, got {value}")
    return value


def _float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}, got {value}")
    return value


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip().lower() for x in os.environ.get(name, default).split(",") if x.strip()]


@dataclass
class Settings:
    env: str = "development"
    secret_key: str = ""
    database_path: Path = BASE_DIR / "instance" / "radynta.db"
    site_url: str = "https://radynta.com"
    canonical_host: str = "radynta.com"
    redirect_hosts: list[str] = field(default_factory=list)
    contact_email: str = ""
    contact_phone: str = ""
    # Outbound email (optional). If unset, enquiries are stored only.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    enquiry_notify_to: str = ""
    # Audit crawler limits
    audit_max_pages: int = 25
    audit_request_delay: float = 1.0
    audit_timeout: float = 10.0
    audit_max_bytes: int = 2_000_000
    audit_user_agent: str = "RADYNTA-AuditBot/0.1 (+https://radynta.com/bot)"
    # AI provider credentials (optional)
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar"
    openai_api_key: str = ""
    openai_model: str = ""
    visibility_request_delay: float = 2.0

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from and self.enquiry_notify_to)


def load_settings(env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or BASE_DIR / ".env")
    env = os.environ.get("RADYNTA_ENV", "development").strip().lower()
    if env not in {"development", "production", "test"}:
        raise ConfigError("RADYNTA_ENV must be development, production or test")

    secret = os.environ.get("RADYNTA_SECRET_KEY", "")
    if env == "production" and len(secret) < 32:
        raise ConfigError(
            "RADYNTA_SECRET_KEY must be set to a random value of 32+ characters in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not secret:
        secret = "dev-only-insecure-key-change-me"  # never used in production (checked above)

    db_path = os.environ.get("DATABASE_PATH")
    site_url = os.environ.get("SITE_URL", "https://radynta.com").rstrip("/")
    if not site_url.startswith(("http://", "https://")):
        raise ConfigError("SITE_URL must start with http:// or https://")

    return Settings(
        env=env,
        secret_key=secret,
        database_path=Path(db_path) if db_path else BASE_DIR / "instance" / "radynta.db",
        site_url=site_url,
        canonical_host=os.environ.get("CANONICAL_HOST", "radynta.com").strip().lower(),
        redirect_hosts=_list("REDIRECT_HOSTS", "radynta.in,www.radynta.in,www.radynta.com"),
        contact_email=os.environ.get("CONTACT_EMAIL", "").strip(),
        contact_phone=os.environ.get("CONTACT_PHONE", "").strip(),
        smtp_host=os.environ.get("SMTP_HOST", "").strip(),
        smtp_port=_int("SMTP_PORT", 587, 1, 65535),
        smtp_user=os.environ.get("SMTP_USER", "").strip(),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        smtp_from=os.environ.get("SMTP_FROM", "").strip(),
        enquiry_notify_to=os.environ.get("ENQUIRY_NOTIFY_TO", "").strip(),
        audit_max_pages=_int("AUDIT_MAX_PAGES", 25, 1, 200),
        audit_request_delay=_float("AUDIT_REQUEST_DELAY", 1.0, 0.0, 30.0),
        audit_timeout=_float("AUDIT_TIMEOUT", 10.0, 1.0, 60.0),
        audit_max_bytes=_int("AUDIT_MAX_BYTES", 2_000_000, 10_000, 20_000_000),
        perplexity_api_key=os.environ.get("PERPLEXITY_API_KEY", "").strip(),
        perplexity_model=os.environ.get("PERPLEXITY_MODEL", "sonar").strip(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        openai_model=os.environ.get("OPENAI_MODEL", "").strip(),
        visibility_request_delay=_float("VISIBILITY_REQUEST_DELAY", 2.0, 0.0, 60.0),
    )
