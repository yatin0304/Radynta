"""RADYNTA Logistics Visibility Diagnostic — internal 100-point framework.

This is RADYNTA's own diagnostic, NOT an official Google/ChatGPT/Gemini/Perplexity
ranking or score. Dimensions that could not be measured are excluded from the
denominator (reported as "not measured") instead of being scored as zero.

Dimension weights: AI answer visibility 25, technical SEO 20, service & route
relevance 20, trust & credibility 15, content quality 10, conversion readiness 10.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

DIMENSIONS = {
    "ai_visibility": ("AI answer visibility", 25),
    "technical": ("Technical SEO and crawlability", 20),
    "relevance": ("Service and route relevance", 20),
    "trust": ("Trust and business credibility", 15),
    "content": ("Content quality", 10),
    "conversion": ("Conversion readiness", 10),
}


@dataclass
class Check:
    dimension: str
    code: str
    label: str
    possible: float
    awarded: float = 0.0
    measured: bool = True
    evidence: str = ""
    urls: list[str] = field(default_factory=list)
    limitation: str = ""


def _ratio(n: int, d: int) -> float:
    return n / d if d else 0.0


def _short(urls, limit=8):
    return list(urls)[:limit]


def _term_re(term: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term.lower()) + r"(?![A-Za-z0-9])")


def _html_pages(pages: list[dict]) -> list[dict]:
    return [p for p in pages if p.get("data") and p.get("status_code") and 200 <= p["status_code"] < 300]


def score_audit(site: dict, pages: list[dict], client: dict, visibility: dict | None = None) -> dict:
    """Return the full scorecard dict. `pages` items: url, final_url, status_code, data, error."""
    checks: list[Check] = []
    ok_pages = _html_pages(pages)
    n_ok = len(ok_pages)
    home = next((p for p in pages if p["url"] == site.get("start_url")), pages[0] if pages else None)

    # ------------------------------------------------------------ technical (20)
    home_ok = bool(home and home.get("status_code") and 200 <= home["status_code"] < 300)
    https_ok = bool(site.get("https"))
    c = Check("technical", "T1", "Homepage reachable over HTTPS", 3)
    c.awarded = 3 if (home_ok and https_ok) else 1 if home_ok else 0
    c.evidence = (f"Homepage {home['url']} returned {home.get('status_code')} (final URL {home.get('final_url')})"
                  if home else "Homepage could not be fetched")
    if home and home.get("error"):
        c.evidence += f"; error: {home['error']}"
    checks.append(c)

    rs = site.get("robots_status")
    c = Check("technical", "T2", "robots.txt accessible and not blocking the site", 2)
    if site.get("robots_blocks_all"):
        c.awarded, c.evidence = 0, "robots.txt disallows crawling of the homepage for all user agents"
    elif rs == 200:
        c.awarded, c.evidence = 2, "robots.txt returned 200 and permits crawling of the homepage"
    elif rs == 404:
        c.awarded, c.evidence = 1, "robots.txt not found (404). Crawling is permitted, but no sitemap is declared there"
    else:
        c.awarded, c.evidence = 0, f"robots.txt returned {rs}"
    checks.append(c)

    c = Check("technical", "T3", "XML sitemap available", 2)
    if site.get("sitemap_status") == 200 and (site.get("sitemap_url_count") or 0) > 0:
        c.awarded, c.evidence = 2, f"Sitemap {site.get('sitemap_url')} lists {site.get('sitemap_url_count')} URLs"
    elif site.get("sitemap_status") == 200:
        c.awarded, c.evidence = 1, f"Sitemap {site.get('sitemap_url')} returned 200 but no <loc> URLs were parsed"
    else:
        c.evidence = f"No sitemap found (checked {site.get('sitemap_url') or '/sitemap.xml'}, status {site.get('sitemap_status')})"
    checks.append(c)

    noindex = [p["final_url"] for p in ok_pages if p["data"].get("noindex")]
    c = Check("technical", "T4", "Pages indexable (no unintended noindex)", 3)
    home_noindex = bool(home and home.get("data", {}).get("noindex"))
    c.awarded = 0 if home_noindex else round(3 * (1 - _ratio(len(noindex), n_ok)), 2) if n_ok else 0
    c.evidence = (f"{len(noindex)} of {n_ok} crawled pages carry a noindex directive"
                  + ("; the HOMEPAGE is noindex" if home_noindex else ""))
    c.urls = _short(noindex)
    checks.append(c)

    titles = [p["data"].get("title", "") for p in ok_pages]
    dup_titles = {t for t in titles if t and titles.count(t) > 1}
    bad_title = [p["final_url"] for p in ok_pages
                 if not (10 <= len(p["data"].get("title", "")) <= 65) or p["data"].get("title") in dup_titles]
    c = Check("technical", "T5", "Unique, well-sized page titles", 3)
    c.awarded = round(3 * (1 - _ratio(len(bad_title), n_ok)), 2) if n_ok else 0
    c.evidence = (f"{len(bad_title)} of {n_ok} pages have a missing, too short/long (outside 10–65 chars) or duplicated title; "
                  f"{len(dup_titles)} duplicated title text(s)")
    c.urls = _short(bad_title)
    checks.append(c)

    descs = [p["data"].get("meta_description", "") for p in ok_pages]
    dup_desc = {d for d in descs if d and descs.count(d) > 1}
    bad_desc = [p["final_url"] for p in ok_pages
                if not (50 <= len(p["data"].get("meta_description", "")) <= 170) or p["data"].get("meta_description") in dup_desc]
    c = Check("technical", "T6", "Unique meta descriptions", 2)
    c.awarded = round(2 * (1 - _ratio(len(bad_desc), n_ok)), 2) if n_ok else 0
    c.evidence = f"{len(bad_desc)} of {n_ok} pages have a missing, poorly sized (outside 50–170 chars) or duplicated meta description"
    c.urls = _short(bad_desc)
    checks.append(c)

    bad_h1 = [p["final_url"] for p in ok_pages if len(p["data"].get("h1", [])) != 1]
    c = Check("technical", "T7", "Exactly one H1 per page", 2)
    c.awarded = round(2 * (1 - _ratio(len(bad_h1), n_ok)), 2) if n_ok else 0
    c.evidence = f"{len(bad_h1)} of {n_ok} pages have zero or multiple H1 headings"
    c.urls = _short(bad_h1)
    checks.append(c)

    site_host = site.get("site_host", "")
    def _path(u):
        return (urlsplit(u).path or "/").rstrip("/") or "/"

    def _canon_ok(p):
        can = p["data"].get("canonical")
        if not can:
            return False
        host = (urlsplit(can).hostname or "").lower()
        # Must stay on-site and point at the page itself (a common CMS bug points every page at the homepage).
        return host.removeprefix("www.") == site_host and _path(can) == _path(p["final_url"])
    bad_canon = [p["final_url"] for p in ok_pages if not _canon_ok(p)]
    to_home = sum(1 for p in ok_pages if p["data"].get("canonical") and _path(p["data"]["canonical"]) == "/" and _path(p["final_url"]) != "/")
    c = Check("technical", "T8", "Self-referencing canonical URLs", 1)
    c.awarded = round(1 * (1 - _ratio(len(bad_canon), n_ok)), 2) if n_ok else 0
    c.evidence = (f"{len(bad_canon)} of {n_ok} pages lack a canonical tag, point it to another domain, or point it to a different URL"
                  + (f"; {to_home} inner page(s) declare the HOMEPAGE as canonical, which asks search engines to ignore them" if to_home else ""))
    c.limitation = "A canonical pointing elsewhere can be intentional for duplicate pages; confirm before changing."
    c.urls = _short(bad_canon)
    checks.append(c)

    broken = [p["url"] for p in pages if (p.get("status_code") or 0) >= 400 or (p.get("status_code") is None and p.get("error"))]
    c = Check("technical", "T9", "No broken internal pages among crawled URLs", 2)
    share = _ratio(len(broken), len(pages))
    c.awarded = 0 if share > 0.10 else round(2 * (1 - share * 10), 2) if broken else 2
    c.evidence = f"{len(broken)} of {len(pages)} crawled internal URLs returned an error (4xx/5xx or fetch failure)"
    c.urls = _short(broken)
    c.limitation = "Only crawled URLs were checked; internal URLs beyond the page limit were not tested."
    checks.append(c)

    # ------------------------------------------------------------ relevance (20)
    services = [s for s in client.get("services", []) if s.strip()]
    geos = [g for g in client.get("geographies", []) if g.strip()]

    def _coverage(terms: list[str]) -> tuple[float, dict[str, str]]:
        detail: dict[str, str] = {}
        total = 0.0
        for term in terms:
            rx = _term_re(term)
            strong = [p for p in ok_pages if rx.search((p["data"].get("title", "") + " " + " ".join(p["data"].get("h1", []))).lower())]
            weak = [p for p in ok_pages if rx.search(p["data"].get("body_excerpt", "").lower())]
            if strong:
                total += 1
                detail[term] = f"in title/H1 ({urlsplit(strong[0]['final_url']).path or '/'})"
            elif weak:
                total += 0.5
                detail[term] = "body text only"
            else:
                detail[term] = "not found"
        return (total / len(terms) if terms else 0.0), detail

    c = Check("relevance", "S1", "Configured services appear in titles/H1s", 8)
    if services:
        cov, detail = _coverage(services)
        c.awarded = round(8 * cov, 2)
        c.evidence = "; ".join(f"{k}: {v}" for k, v in detail.items())
    else:
        c.measured, c.evidence = False, "No services configured for this client"
    checks.append(c)

    c = Check("relevance", "S2", "Dedicated pages for each core service", 4)
    if services:
        have = []
        for term in services:
            rx = _term_re(term)
            slug_rx = re.compile(re.escape(re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")))
            if any(slug_rx.search(urlsplit(p["final_url"]).path.lower()) or rx.search(" ".join(p["data"].get("h1", [])).lower())
                   for p in ok_pages if urlsplit(p["final_url"]).path not in ("", "/")):
                have.append(term)
        c.awarded = round(4 * _ratio(len(have), len(services)), 2)
        missing = [s for s in services if s not in have]
        c.evidence = f"{len(have)} of {len(services)} services have a dedicated page" + (f"; missing: {', '.join(missing)}" if missing else "")
    else:
        c.measured, c.evidence = False, "No services configured for this client"
    checks.append(c)

    c = Check("relevance", "S3", "Target cities, states and routes covered", 6)
    if geos:
        cov, detail = _coverage(geos)
        c.awarded = round(6 * cov, 2)
        c.evidence = "; ".join(f"{k}: {v}" for k, v in detail.items())
    else:
        c.measured, c.evidence = False, "No target geographies/routes configured for this client"
    checks.append(c)

    c = Check("relevance", "S4", "Homepage states what the company does", 2)
    if home and home.get("data") and services:
        head_text = (home["data"].get("title", "") + " " + " ".join(home["data"].get("h1", []))).lower()
        hit = [s for s in services + ["logistics", "transport", "freight", "warehousing", "courier", "cargo", "3pl", "shipping"]
               if _term_re(s).search(head_text)]
        c.awarded = 2 if hit else 0
        c.evidence = f"Homepage title/H1: “{head_text[:140]}”" + ("" if hit else " — no service term found")
    else:
        c.measured, c.evidence = False, "Homepage not parsed or no services configured"
    checks.append(c)

    # ------------------------------------------------------------ trust (15)
    def _any(key):
        return [p["final_url"] for p in ok_pages if p["data"].get(key)]

    phones = _any("phones") + _any("tel_links")
    c = Check("trust", "R1", "Phone number visible", 3)
    c.awarded = 3 if phones else 0
    c.evidence = f"Phone number or tel: link found on {len(set(phones))} page(s)" if phones else "No phone number detected on crawled pages"
    c.limitation = "Numbers rendered only as images or by JavaScript are not detected."
    checks.append(c)

    emails = _any("emails") + _any("mailto_links")
    c = Check("trust", "R2", "Business email visible", 2)
    c.awarded = 2 if emails else 0
    c.evidence = f"Email address found on {len(set(emails))} page(s)" if emails else "No email address detected"
    checks.append(c)

    addr = _any("address_signal")
    c = Check("trust", "R3", "Physical address with PIN code", 3)
    c.awarded = 3 if addr else 0
    c.evidence = f"Address-like text with PIN code on {len(addr)} page(s)" if addr else "No address with a PIN code detected"
    c.limitation = "Heuristic detection; a human reviewer should confirm the address is complete and matches the Google Business Profile."
    checks.append(c)

    about = [p["final_url"] for p in ok_pages if re.search(r"about", urlsplit(p["final_url"]).path, re.I)]
    about_nav = any("about" in t for p in ok_pages for t in p["data"].get("nav_texts", []))
    c = Check("trust", "R4", "About / company page", 2)
    c.awarded = 2 if (about or about_nav) else 0
    c.evidence = f"About page: {about[0]}" if about else ("About link present in navigation" if about_nav else "No About page found")
    checks.append(c)

    org_types = {"Organization", "LocalBusiness", "MovingCompany", "Corporation", "ProfessionalService", "AutomotiveBusiness"}
    org = [p["final_url"] for p in ok_pages if org_types & set(p["data"].get("schema_types", []))]
    schema_err = [p["final_url"] for p in ok_pages if p["data"].get("schema_errors")]
    c = Check("trust", "R5", "Organization / LocalBusiness structured data", 2)
    c.awarded = 2 if org else 0
    c.evidence = (f"Organization-type JSON-LD on {len(org)} page(s)" if org else "No Organization or LocalBusiness JSON-LD detected")
    if schema_err:
        c.evidence += f"; {len(schema_err)} page(s) contain JSON-LD that fails to parse"
        c.urls = _short(schema_err)
    checks.append(c)

    gst = _any("gstin")
    privacy = [p["final_url"] for p in ok_pages if re.search(r"privacy", urlsplit(p["final_url"]).path, re.I)] or \
              ([1] if any("privacy" in t for p in ok_pages for t in p["data"].get("nav_texts", [])) else [])
    c = Check("trust", "R6", "Business identity signals (GSTIN, privacy policy)", 3)
    c.awarded = (2 if gst else 0) + (1 if privacy else 0)
    c.evidence = f"GSTIN shown: {'yes' if gst else 'no'}; privacy policy: {'yes' if privacy else 'no'}"
    checks.append(c)

    # ------------------------------------------------------------ content (10)
    thin = [p["final_url"] for p in ok_pages if p["data"].get("word_count", 0) < 250]
    c = Check("content", "C1", "Pages with substantive content (250+ words)", 4)
    c.awarded = round(4 * (1 - _ratio(len(thin), n_ok)), 2) if n_ok else 0
    c.evidence = f"{len(thin)} of {n_ok} pages have fewer than 250 words of visible text"
    c.urls = _short(thin)
    c.limitation = "Word count is a proxy; it does not measure accuracy or usefulness."
    checks.append(c)

    structured = [p for p in ok_pages if p["data"].get("h2_count", 0) >= 2 and not p["data"].get("heading_skip")]
    c = Check("content", "C2", "Clear heading structure (2+ H2s, no skipped levels)", 3)
    c.awarded = round(3 * _ratio(len(structured), n_ok), 2) if n_ok else 0
    c.evidence = f"{len(structured)} of {n_ok} pages have at least two H2 sections without skipped heading levels"
    checks.append(c)

    faq = [p["final_url"] for p in ok_pages
           if len(p["data"].get("question_headings", [])) >= 3 or "FAQPage" in p["data"].get("schema_types", [])]
    c = Check("content", "C3", "Question-and-answer content buyers can quote", 3)
    c.awarded = 3 if faq else 0
    c.evidence = f"FAQ-style content on {len(faq)} page(s)" if faq else "No page with 3+ question headings or FAQPage markup"
    c.urls = _short(faq)
    checks.append(c)

    # ------------------------------------------------------------ conversion (10)
    tel = _any("tel_links")
    c = Check("conversion", "V1", "Click-to-call link", 3)
    c.awarded = 3 if tel else 0
    c.evidence = f"tel: links on {len(tel)} page(s)" if tel else "No tel: links — mobile visitors cannot tap to call"
    checks.append(c)

    wa = _any("whatsapp_links")
    c = Check("conversion", "V2", "WhatsApp contact link", 2)
    c.awarded = 2 if wa else 0
    c.evidence = f"WhatsApp links on {len(wa)} page(s)" if wa else "No WhatsApp link detected"
    checks.append(c)

    forms = _any("forms")
    c = Check("conversion", "V3", "Enquiry / quote form", 3)
    c.awarded = 3 if forms else 0
    c.evidence = f"Enquiry-style forms on {len(forms)} page(s)" if forms else "No enquiry form detected (search forms excluded)"
    c.limitation = "Forms injected by third-party scripts after page load may not be detected."
    checks.append(c)

    cta = home.get("data", {}).get("cta_matches", []) if home else []
    c = Check("conversion", "V4", "Clear enquiry call-to-action on homepage", 2)
    c.awarded = 2 if cta else 0
    c.evidence = f"Homepage CTAs: {', '.join(cta)}" if cta else "No quote/enquiry call-to-action text on the homepage"
    checks.append(c)

    # ------------------------------------------------------------ AI visibility (25)
    vis = visibility or {}
    valid = vis.get("valid_runs") or 0
    for code, label, pts, key in (("A1", "Brand mentioned in AI answers", 15, "brand_mention_rate"),
                                  ("A2", "Client website cited as a source", 10, "client_citation_rate")):
        c = Check("ai_visibility", code, label, pts)
        if valid and vis.get(key) is not None:
            c.awarded = round(pts * vis[key], 2)
            c.evidence = (f"{vis[key] * 100:.0f}% of {valid} valid responses "
                          f"({vis.get('platforms_label', 'tested platforms')})")
            c.limitation = "Small samples; AI answers vary between runs, locations and accounts."
        else:
            c.measured = False
            c.evidence = "No valid AI visibility responses collected for this audit"
        checks.append(c)

    return build_scorecard(checks)


def build_scorecard(checks: list[Check]) -> dict:
    dims = {}
    for key, (label, weight) in DIMENSIONS.items():
        dc = [c for c in checks if c.dimension == key]
        measured = [c for c in dc if c.measured]
        dims[key] = {
            "label": label,
            "weight": weight,
            "possible": round(sum(c.possible for c in measured), 2),
            "awarded": round(sum(c.awarded for c in measured), 2),
            "measured": bool(measured),
            "fully_measured": len(measured) == len(dc),
            "checks": [asdict(c) for c in dc],
        }
    awarded = round(sum(d["awarded"] for d in dims.values()), 2)
    possible = round(sum(d["possible"] for d in dims.values()), 2)
    return {
        "framework": "RADYNTA Logistics Visibility Diagnostic v0.1 (internal; not an official search-engine score)",
        "dimensions": dims,
        "awarded": awarded,
        "measured_possible": possible,
        "framework_possible": 100,
        "normalized": round(100 * awarded / possible) if possible else None,
    }


def severity_for(check: dict) -> str | None:
    if not check["measured"] or check["possible"] <= 0:
        return None
    shortfall = (check["possible"] - check["awarded"]) / check["possible"]
    if shortfall <= 0.001:
        return None
    if shortfall >= 0.75 and check["possible"] >= 3:
        return "high"
    if shortfall >= 0.4:
        return "medium"
    return "low"
