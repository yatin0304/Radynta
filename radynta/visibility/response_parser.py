"""Brand-mention and citation extraction from AI answers.

A *mention* means the brand name appears in the answer text.
A *citation* means a source URL (returned by the platform, or written in the
answer) points to a domain. The two are tracked separately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

URL_RE = re.compile(r"https?://[^\s<>\"'\]\[}{|\\^`]+", re.I)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)", re.I)
TRAILING = ".,;:!?'\"*_"

# Words that, on their own, are too generic to count as an unambiguous brand match.
GENERIC_WORDS = {
    "express", "logistics", "cargo", "transport", "transports", "global", "fast", "swift", "prime", "united",
    "national", "india", "indian", "freight", "shipping", "movers", "packers", "carriers", "roadways", "safe",
    "speed", "quick", "star", "royal", "city", "metro", "first", "best", "supply", "chain", "trans", "line",
}


def extract_urls(text: str) -> list[str]:
    found: list[str] = []
    for m in MD_LINK_RE.finditer(text or ""):
        found.append(m.group(1))
    for m in URL_RE.finditer(text or ""):
        found.append(m.group(0))
    out, seen = [], set()
    for url in found:
        url = url.rstrip(TRAILING)
        while url.endswith(")") and url.count("(") < url.count(")"):
            url = url[:-1].rstrip(TRAILING)
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def domain_of(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower().strip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def domain_matches(domain: str, target: str) -> bool:
    """True if domain is target or a subdomain of it (www-insensitive)."""
    target = target.lower().removeprefix("www.").strip(".")
    return bool(target) and (domain == target or domain.endswith("." + target))


def _name_pattern(name: str) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(name.strip()) + r"(?![\w])", re.I)


@dataclass
class Mention:
    mentioned: bool
    matched: str | None = None
    context: str | None = None
    ambiguous: bool = False
    reason: str | None = None


def detect_mention(text: str, names: list[str], context_chars: int = 140) -> Mention:
    """Find the first match of any name/alias. Longer names are tried first."""
    text = text or ""
    for name in sorted({n.strip() for n in names if n and n.strip()}, key=len, reverse=True):
        m = _name_pattern(name).search(text)
        if not m:
            continue
        start, end = max(0, m.start() - context_chars), min(len(text), m.end() + context_chars)
        context = ("…" if start else "") + text[start:end].replace("\n", " ") + ("…" if end < len(text) else "")
        tokens = re.findall(r"\w+", name.lower())
        ambiguous, reason = False, None
        if len(name.strip()) < 4:
            ambiguous, reason = True, f"alias '{name}' is shorter than 4 characters"
        elif all(t in GENERIC_WORDS for t in tokens):
            ambiguous, reason = True, f"alias '{name}' consists only of generic logistics words"
        return Mention(True, name, context, ambiguous, reason)
    return Mention(False)


@dataclass
class ParsedCitation:
    url: str
    domain: str
    origin: str  # 'provider' or 'text'
    is_client_domain: bool
    competitor_id: int | None = None


@dataclass
class ParsedResponse:
    brand: Mention
    citations: list[ParsedCitation] = field(default_factory=list)
    competitor_mentions: list[dict] = field(default_factory=list)

    @property
    def client_cited(self) -> bool:
        return any(c.is_client_domain for c in self.citations)


def parse_response(text: str, provider_citations: list[str], client: dict) -> ParsedResponse:
    names = [client["brand_name"], *client.get("brand_aliases", [])]
    brand = detect_mention(text, names)
    client_domains = [client["primary_domain"], *client.get("extra_domains", [])]
    competitors = client.get("competitors", [])

    citations: list[ParsedCitation] = []
    seen: set[str] = set()
    for origin, urls in (("provider", provider_citations or []), ("text", extract_urls(text))):
        for url in urls:
            if not isinstance(url, str) or not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            dom = domain_of(url)
            if not dom:
                continue
            comp_id = next((c["id"] for c in competitors if c.get("domain") and domain_matches(dom, c["domain"])), None)
            citations.append(ParsedCitation(url, dom, origin, any(domain_matches(dom, d) for d in client_domains), comp_id))

    comp_mentions = []
    for comp in competitors:
        m = detect_mention(text, [comp["name"], *comp.get("aliases", [])])
        if m.mentioned:
            comp_mentions.append({"competitor_id": comp["id"], "name": comp["name"], "context": m.context,
                                  "ambiguous": m.ambiguous})
    return ParsedResponse(brand, citations, comp_mentions)
