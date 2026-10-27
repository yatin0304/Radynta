"""Polite, bounded, same-site crawler + per-page technical/content extraction."""
from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .safe_fetch import FetchResult, SafeFetcher

SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".zip", ".rar", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".mp4", ".mp3", ".avi", ".mov", ".css", ".js", ".json", ".xml", ".woff", ".woff2",
)
# Private/transactional areas we never crawl by default.
SKIP_PATH_PATTERNS = re.compile(
    r"/(wp-admin|wp-login|admin|login|signin|sign-in|logout|account|my-account|cart|checkout|dashboard|portal|cgi-bin)(/|$)",
    re.I,
)
PHONE_RE = re.compile(
    r"(?:\+91[\s-]?)?\b[6-9]\d{4}[\s-]?\d{5}\b"          # Indian mobile
    r"|\b0\d{2,4}[\s-]\d{6,8}\b"                          # Indian landline with STD code
    r"|\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b"  # international
)
ADDRESS_WORDS_RE = re.compile(
    r"\b(road|rd\.?|marg|nagar|street|st\.?|lane|sector|plot|floor|building|bldg|complex|estate|midc|highway|"
    r"near|opp\.?|east|west|district|taluka|warehouse no|gala|unit no)\b",
    re.I,
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PIN_RE = re.compile(r"\b[1-9]\d{2}\s?\d{3}\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
CTA_RE = re.compile(r"\b(get (a )?(free )?quote|request (a )?quote|get quote|enquir(e|y)|inquir(e|y)|contact us|book (a )?(shipment|truck|pickup|call)|track (your )?shipment|get in touch|call us)\b", re.I)


def normalize_host(host: str) -> str:
    host = (host or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def text_of(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def parse_page(url: str, html: str, site_host: str) -> dict:
    """Extract technical, content, trust and conversion facts from one HTML page."""
    soup = BeautifulSoup(html, "lxml")
    head = soup.head or soup

    title = text_of(soup.title) if soup.title else ""
    meta_desc = ""
    robots_meta = ""
    viewport = False
    og = {}
    for m in soup.find_all("meta"):
        name = (m.get("name") or "").lower()
        prop = (m.get("property") or "").lower()
        content = (m.get("content") or "").strip()
        if name == "description" and not meta_desc:
            meta_desc = content
        elif name in ("robots", "googlebot") and content:
            robots_meta = (robots_meta + "," + content).strip(",").lower()
        elif name == "viewport":
            viewport = True
        elif prop.startswith("og:"):
            og[prop] = content

    canonical = ""
    for link in head.find_all("link"):
        rels = [r.lower() for r in (link.get("rel") or [])]
        if "canonical" in rels and link.get("href"):
            canonical = urljoin(url, link["href"].strip())
            break

    headings = [{"level": int(h.name[1]), "text": text_of(h)[:200]} for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    h1s = [h["text"] for h in headings if h["level"] == 1]
    skipped = any(b["level"] - a["level"] > 1 for a, b in zip(headings, headings[1:]))

    # Structured data (JSON-LD only; microdata noted as presence)
    schema_types: list[str] = []
    schema_errors = 0
    for script in soup.find_all("script", attrs={"type": re.compile(r"application/ld\+json", re.I)}):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            schema_errors += 1
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                t = node.get("@type")
                if isinstance(t, str):
                    schema_types.append(t)
                elif isinstance(t, list):
                    schema_types.extend(str(x) for x in t)
                if isinstance(node.get("@graph"), list):
                    stack.extend(node["@graph"])
    has_microdata = bool(soup.find(attrs={"itemtype": True}))

    # Links
    internal, external = set(), set()
    tel_links = mail_links = whatsapp_links = 0
    nav_texts = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if low.startswith("tel:"):
            tel_links += 1
            continue
        if low.startswith("mailto:"):
            mail_links += 1
            continue
        if "wa.me/" in low or "api.whatsapp.com" in low or "whatsapp://" in low:
            whatsapp_links += 1
            continue
        if low.startswith(("javascript:", "#", "data:")):
            continue
        absolute = normalize_url(urljoin(url, href))
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https"):
            continue
        if normalize_host(parts.hostname or "") == site_host:
            internal.add(absolute)
            nav_texts.append(text_of(a).lower()[:60])
        else:
            external.add(absolute)

    # Body text (drop script/style/nav noise for word counts)
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    body_text = text_of(soup.body or soup)
    words = re.findall(r"[A-Za-zऀ-ॿ]{2,}", body_text)

    forms = []
    for f in soup.find_all("form"):
        inputs = f.find_all(["input", "textarea", "select"])
        visible = [i for i in inputs if (i.get("type") or "text").lower() not in ("hidden", "submit", "button")]
        is_search = (f.get("role") == "search") or any((i.get("type") or "").lower() == "search" or (i.get("name") or "").lower() in ("s", "q", "search") for i in inputs)
        if len(visible) >= 2 and not is_search:
            forms.append(len(visible))

    imgs = soup.find_all("img")
    missing_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())
    question_headings = [h["text"] for h in headings if h["level"] >= 2 and h["text"].endswith("?")]

    return {
        "title": title,
        "meta_description": meta_desc,
        "robots_meta": robots_meta,
        "noindex": "noindex" in robots_meta,
        "canonical": canonical,
        "lang": ((soup.html.get("lang") if soup.html else "") or "").strip(),
        "viewport": viewport,
        "og_title": bool(og.get("og:title")),
        "h1": h1s,
        "headings": headings[:60],
        "heading_skip": skipped,
        "h2_count": sum(1 for h in headings if h["level"] == 2),
        "question_headings": question_headings[:20],
        "schema_types": sorted(set(schema_types)),
        "schema_errors": schema_errors,
        "microdata": has_microdata,
        "internal_links": sorted(internal),
        "external_link_count": len(external),
        "nav_texts": nav_texts[:80],
        "tel_links": tel_links,
        "mailto_links": mail_links,
        "whatsapp_links": whatsapp_links,
        "forms": forms,
        "cta_matches": sorted({m.group(0).lower() for m in CTA_RE.finditer(body_text)})[:10],
        "word_count": len(words),
        "images": len(imgs),
        "images_missing_alt": missing_alt,
        "phones": sorted({m.group(0).strip() for m in PHONE_RE.finditer(body_text)})[:5],
        "emails": sorted({m.group(0) for m in EMAIL_RE.finditer(body_text)})[:5],
        "pin_codes": sorted({m.group(0) for m in PIN_RE.finditer(body_text)})[:5],
        "address_signal": bool(PIN_RE.search(body_text) and ADDRESS_WORDS_RE.search(body_text)),
        "gstin": sorted({m.group(0) for m in GSTIN_RE.finditer(body_text)})[:3],
        "body_excerpt": body_text[:20000],
    }


@dataclass
class PageResult:
    url: str
    final_url: str
    status_code: int | None
    redirect_chain: list[dict]
    data: dict
    error: str | None = None
    depth: int = 0


@dataclass
class CrawlResult:
    start_url: str
    site_host: str
    pages: list[PageResult] = field(default_factory=list)
    robots_status: int | None = None
    robots_txt: str = ""
    robots_blocks_all: bool = False
    sitemap_url: str | None = None
    sitemap_status: int | None = None
    sitemap_url_count: int | None = None
    https: bool = False
    notes: list[str] = field(default_factory=list)
    discovered_not_crawled: int = 0


class SiteCrawler:
    def __init__(self, fetcher: SafeFetcher, *, max_pages: int = 25, delay: float = 1.0,
                 user_agent: str = "RADYNTA-AuditBot", sleep=time.sleep) -> None:
        self.fetcher = fetcher
        self.max_pages = max_pages
        self.delay = delay
        self.user_agent = user_agent
        self.sleep = sleep
        self._first_request = True

    def _get(self, url: str) -> FetchResult:
        if not self._first_request and self.delay:
            self.sleep(self.delay)
        self._first_request = False
        return self.fetcher.fetch(url)

    def crawl(self, start_url: str) -> CrawlResult:
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
        start_url = normalize_url(start_url)
        parts = urlsplit(start_url)
        site_host = normalize_host(parts.hostname or "")
        result = CrawlResult(start_url=start_url, site_host=site_host)
        origin = f"{parts.scheme}://{parts.netloc}"

        # robots.txt
        robots = urllib.robotparser.RobotFileParser()
        rr = self._get(origin + "/robots.txt")
        result.robots_status = rr.status_code
        sitemap_candidates: list[str] = []
        if rr.ok and "html" not in rr.content_type:
            result.robots_txt = rr.text()[:20000]
            robots.parse(result.robots_txt.splitlines())
            for line in result.robots_txt.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_candidates.append(line.split(":", 1)[1].strip())
            result.robots_blocks_all = not robots.can_fetch("*", origin + "/")
        else:
            robots.parse([])  # missing robots.txt => everything allowed
            if rr.error:
                result.notes.append(f"robots.txt fetch error: {rr.error}")

        # sitemap
        seeds: list[str] = []
        for sm_url in (sitemap_candidates or [origin + "/sitemap.xml"])[:2]:
            sm = self._get(sm_url)
            result.sitemap_url, result.sitemap_status = sm_url, sm.status_code
            if sm.ok:
                locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.text(), re.I)
                result.sitemap_url_count = len(locs)
                seeds = [normalize_url(u) for u in locs if u.startswith("http")]
                break

        queue: deque[tuple[str, int]] = deque([(start_url, 0)])
        seen = {start_url}
        for s in seeds[: self.max_pages]:
            if normalize_host(urlsplit(s).hostname or "") == site_host and s not in seen and not s.endswith(".xml"):
                seen.add(s)
                queue.append((s, 1))
        discovered: set[str] = set(seen)

        while queue and len(result.pages) < self.max_pages:
            url, depth = queue.popleft()
            if not robots.can_fetch(self.user_agent, url):
                result.notes.append(f"skipped (robots.txt disallow): {url}")
                continue
            fr = self._get(url)
            page = PageResult(url=url, final_url=fr.final_url, status_code=fr.status_code,
                              redirect_chain=fr.redirect_chain, data={}, error=fr.error, depth=depth)
            final_host = normalize_host(urlsplit(fr.final_url).hostname or "")
            if fr.ok and "html" in (fr.content_type or "text/html") and final_host == site_host:
                page.data = parse_page(fr.final_url, fr.text(), site_host)
                if fr.truncated:
                    result.notes.append(f"response truncated at size limit: {url}")
                for link in page.data["internal_links"]:
                    discovered.add(link)
                    if link in seen or self._skip(link):
                        continue
                    seen.add(link)
                    queue.append((link, depth + 1))
            elif fr.ok and final_host != site_host:
                page.error = page.error or f"redirected off-site to {fr.final_url}"
            if url == start_url:
                result.https = fr.final_url.startswith("https://") and fr.ok
            result.pages.append(page)

        crawled = {p.url for p in result.pages}
        result.discovered_not_crawled = len([u for u in discovered if u not in crawled and not self._skip(u)])
        if result.discovered_not_crawled:
            result.notes.append(
                f"{result.discovered_not_crawled} internal URLs discovered but not crawled (page limit {self.max_pages})."
            )
        return result

    @staticmethod
    def _skip(url: str) -> bool:
        path = urlsplit(url).path.lower()
        return path.endswith(SKIP_EXTENSIONS) or bool(SKIP_PATH_PATTERNS.search(path))
