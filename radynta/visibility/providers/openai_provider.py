"""OpenAI Responses API adapter with the web search tool.

Requires OPENAI_API_KEY and OPENAI_MODEL (choose a model that supports the
web_search tool on your account). Status: implemented against the documented
Responses API format but NOT yet verified with a live key in this repository.
API answers can differ from what users see in the ChatGPT app.
"""
from __future__ import annotations

import json

from .base import Provider, ProviderError, ProviderResult

API_URL = "https://api.openai.com/v1/responses"


class OpenAIWebSearchProvider(Provider):
    platform = "openai-api-websearch"
    required_settings = ("openai_api_key", "openai_model")

    @property
    def model(self) -> str:
        return self.settings.openai_model

    def collect(self, prompt: str, market: str | None = None) -> ProviderResult:
        payload = {"model": self.model, "input": prompt, "tools": [{"type": "web_search"}]}
        data = self._post_json(API_URL, {"Authorization": f"Bearer {self.settings.openai_api_key}"}, payload)
        texts, citations = [], []
        for item in data.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                    for ann in part.get("annotations") or []:
                        url = ann.get("url") if isinstance(ann, dict) else None
                        if isinstance(url, str) and url not in citations:
                            citations.append(url)
        if not texts and isinstance(data.get("output_text"), str):
            texts.append(data["output_text"])
        if not texts:
            raise ProviderError("unexpected response shape: no output_text found")
        return ProviderResult(text="\n".join(texts), citations=citations, model=data.get("model") or self.model,
                              raw_payload=json.dumps(data)[:200_000])
