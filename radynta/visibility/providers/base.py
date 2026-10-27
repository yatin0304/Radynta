"""Provider adapter interface for AI/search answer collection.

Important: API answers are NOT guaranteed to match what a consumer sees in the
ChatGPT/Perplexity/Gemini apps (different models, personalisation, location).
Reports must state which collection method was used.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


class ProviderNotConfigured(RuntimeError):
    """Required credentials/config are missing. Raised before any request is made."""


class ProviderError(RuntimeError):
    """A single collection attempt failed (network, auth, rate limit, bad payload)."""


@dataclass
class ProviderResult:
    text: str
    citations: list[str] = field(default_factory=list)
    model: str | None = None
    raw_payload: str | None = None


class Provider:
    platform: str = "unknown"          # stored on every response, e.g. "perplexity-api"
    required_settings: tuple[str, ...] = ()

    def __init__(self, settings, session=None) -> None:
        self.settings = settings
        missing = [name.upper() for name in self.required_settings if not getattr(settings, name, "")]
        if missing:
            raise ProviderNotConfigured(
                f"{self.platform}: missing configuration {', '.join(missing)}. Set it in .env (see .env.example). "
                "No responses were collected and none were fabricated."
            )
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    @property
    def model(self) -> str | None:
        return None

    def collect(self, prompt: str, market: str | None = None) -> ProviderResult:  # pragma: no cover - interface
        raise NotImplementedError

    def _post_json(self, url: str, headers: dict, payload: dict, retries: int = 2) -> dict:
        last = None
        for attempt in range(retries + 1):
            try:
                resp = self.session.post(url, headers=headers, json=payload, timeout=(10, 90))
            except Exception as exc:
                last = ProviderError(f"request failed: {type(exc).__name__}: {exc}")
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ProviderError("response was not valid JSON") from exc
                body = (resp.text or "")[:300]
                if resp.status_code in (401, 403):
                    raise ProviderError(f"authentication failed ({resp.status_code}); check the API key. {body}")
                last = ProviderError(f"HTTP {resp.status_code}: {body}")
                if resp.status_code not in (408, 409, 429, 500, 502, 503, 504):
                    raise last
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
        raise last or ProviderError("unknown error")
