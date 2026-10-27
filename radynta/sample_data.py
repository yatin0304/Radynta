"""SYNTHETIC sample website for demos and the sample report.

Everything here describes a fictional business ("Sample Roadlines") on a
reserved .example domain. It is served from memory — nothing is fetched from
the internet — and every record created from it is flagged is_sample=1.
"""
from __future__ import annotations

SAMPLE_CLIENT = {
    "slug": "sample-roadlines",
    "name": "Sample Roadlines (fictional)",
    "brand_name": "Sample Roadlines",
    "brand_aliases": ["Sample Roadlines Pvt Ltd"],
    "website_url": "https://www.sample-roadlines.example/",
    "primary_domain": "sample-roadlines.example",
    "extra_domains": [],
    "segment": "Road transport / fleet operator",
    "services": ["full truckload", "part load", "container transport", "ODC transport"],
    "geographies": ["Mumbai", "Pune", "Nashik", "Gujarat"],
    "notes": "SYNTHETIC SAMPLE CLIENT — not a real business.",
    "competitors": [
        {"name": "Example Freight Carriers", "domain": "example-freight.example"},
        {"name": "Demo Logistics Co", "domain": "demo-logistics.example"},
    ],
    "prompts": [
        {"text": "Which transport companies provide full truckload services between Mumbai and Pune?", "geography": "Mumbai–Pune", "service_category": "full truckload", "target_customer": "manufacturers"},
        {"text": "Who offers part load transport from Pune to Nashik?", "geography": "Pune–Nashik", "service_category": "part load", "target_customer": "SMEs"},
        {"text": "Which transporters have 32 ft containers in Maharashtra?", "geography": "Maharashtra", "service_category": "container transport", "target_customer": "manufacturers"},
        {"text": "Reliable ODC transport company for machinery in Gujarat?", "geography": "Gujarat", "service_category": "ODC transport", "target_customer": "engineering firms"},
        {"text": "Best road transport company in Mumbai for industrial goods?", "geography": "Mumbai", "service_category": "full truckload", "target_customer": "manufacturers"},
    ],
}

_BASE = "https://www.sample-roadlines.example"
_FILLER = ("Sample Roadlines operates trucks across western India for manufacturers and distributors. "
           "Our dispatch team plans each load with the shipper, confirms vehicle type and shares tracking updates. ") * 14


def _page(title, desc, h1, body, extra_head=""):
    return (f'<!doctype html><html lang="en"><head><title>{title}</title><meta name="description" content="{desc}">'
            f'<meta name="viewport" content="width=device-width"><link rel="canonical" href="{_BASE}/">{extra_head}</head>'
            f'<body><nav><a href="/">Home</a> <a href="/services/">Services</a> <a href="/about-us/">About Us</a> '
            f'<a href="/contact/">Contact</a> <a href="/fleet/">Fleet</a></nav><h1>{h1}</h1>{body}'
            f'<footer>Call +91 98200 00000 · info@sample-roadlines.example</footer></body></html>')


SAMPLE_SITE = {
    f"{_BASE}/robots.txt": (200, "User-agent: *\nAllow: /\n", {"Content-Type": "text/plain"}),
    f"{_BASE}/sitemap.xml": (404, "not found", None),
    f"{_BASE}/": (200, _page(
        "Sample Roadlines", "", "Welcome to Sample Roadlines",
        f"<h2>Who we are</h2><p>{_FILLER}</p><h2>Our services</h2><p>We provide full truckload transport across Maharashtra.</p>"
        '<p><a href="/services/">Get a quote</a></p>'), None),
    f"{_BASE}/services/": (200, _page(
        "Services | Sample Roadlines", "Full truckload, part load and container transport services from Sample Roadlines for shippers in Maharashtra.",
        "Our Services", "<h2>Full truckload</h2><p>FTL transport from Mumbai and Pune.</p><h2>Part load</h2><p>Part load consolidation on request.</p>"
        '<p>Contact us for a quote.</p><a href="/old-rates/">Old rate card</a>'), None),
    f"{_BASE}/about-us/": (200, _page(
        "About Us | Sample Roadlines", "Sample Roadlines is a fictional transport company used to demonstrate RADYNTA audit reports.",
        "About Sample Roadlines", f"<h2>Our story</h2><p>{_FILLER}</p><h2>Our team</h2><p>{_FILLER[:400]}</p>"), None),
    f"{_BASE}/contact/": (200, _page(
        "Contact | Sample Roadlines", "", "Contact us",
        '<p>Office: Unit 12, Example Industrial Estate, Bhiwandi Road, Thane 421302</p><p><a href="tel:+919820000000">Call us</a></p>'
        '<form><input name="name"><input name="phone"><textarea name="msg"></textarea><button>Send</button></form>'), None),
    f"{_BASE}/fleet/": (200, _page(
        "Services | Sample Roadlines", "Full truckload, part load and container transport services from Sample Roadlines for shippers in Maharashtra.",
        "Our fleet", "<p>20 ft and 32 ft container trucks, open body trucks.</p><h1>Vehicles</h1>"), None),
    f"{_BASE}/old-rates/": (404, "not found", None),
}

SAMPLE_RESPONSES_CSV = "data/sample_responses.csv"


class InMemorySession:
    """Serves SAMPLE_SITE (or any url->(status, body, headers) map) without network access."""

    def __init__(self, routes: dict | None = None):
        self.routes = routes or SAMPLE_SITE

    def get(self, url, **kwargs):
        status, body, headers = self.routes.get(url, (404, "not found", None))
        return _Resp(status, body.encode("utf-8") if isinstance(body, str) else body,
                     headers or {"Content-Type": "text/html; charset=utf-8"})


class _Resp:
    def __init__(self, status, body, headers):
        self.status_code, self._body, self.headers = status, body, headers

    def iter_content(self, chunk_size=16384):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


def sample_resolver(host: str) -> list[str]:
    if not host.endswith(".example"):
        raise OSError("sample resolver only serves .example hosts")
    return ["93.184.216.34"]  # placeholder public address; never contacted
