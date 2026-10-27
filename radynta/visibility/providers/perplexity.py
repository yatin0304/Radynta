"""Perplexity Sonar API adapter (search-grounded answers with source URLs).

Docs: https://docs.perplexity.ai — requires PERPLEXITY_API_KEY.
Status: implemented against the documented chat-completions format but NOT yet
verified with a live key in this repository. Run `flask --app radynta check-provider perplexity`
after adding a key.
"""
from __future__ import annotations

import json

from .base import Provider, ProviderError, ProviderResult

API_URL = "https://api.perplexity.ai/chat/completions"


class PerplexityProvider(Provider):
    platform = "perplexity-api"
    required_settings = ("perplexity_api_key",)

    @property
    def model(self) -> str:
        return self.settings.perplexity_model or "sonar"

    def collect(self, prompt: str, market: str | None = None) -> ProviderResult:
        # The buyer question is sent verbatim. We deliberately add no system prompt
        # that could steer the answer toward or away from any brand.
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        data = self._post_json(API_URL, {"Authorization": f"Bearer {self.settings.perplexity_api_key}"}, payload)
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("unexpected response shape: no choices[0].message.content") from exc
        citations = [c for c in (data.get("citations") or []) if isinstance(c, str)]
        for item in data.get("search_results") or []:
            if isinstance(item, dict) and isinstance(item.get("url"), str) and item["url"] not in citations:
                citations.append(item["url"])
        return ProviderResult(text=text, citations=citations, model=data.get("model") or self.model,
                              raw_payload=json.dumps(data)[:200_000])
