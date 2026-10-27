from .base import Provider, ProviderError, ProviderNotConfigured, ProviderResult
from .openai_provider import OpenAIWebSearchProvider
from .perplexity import PerplexityProvider

PROVIDERS = {
    "perplexity": PerplexityProvider,
    "openai": OpenAIWebSearchProvider,
}


def get_provider(name: str, settings, session=None) -> Provider:
    try:
        cls = PROVIDERS[name]
    except KeyError:
        raise ProviderNotConfigured(f"unknown provider {name!r}; choose from {', '.join(PROVIDERS)}") from None
    return cls(settings, session=session)


__all__ = ["Provider", "ProviderError", "ProviderNotConfigured", "ProviderResult", "PROVIDERS", "get_provider"]
