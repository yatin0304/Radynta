import json
import re

import pytest

from radynta.site.content import ARTICLES, INDUSTRIES, SERVICES
from tests.conftest import csrf_from, old_timer

PAGES = ["/", "/services/", "/about/", "/resources/", "/contact/", "/audit-request/", "/privacy/", "/terms/"] + \
        [f"/services/{s}/" for s in SERVICES] + [f"/industries/{s}/" for s in INDUSTRIES] + [f"/resources/{s}/" for s in ARTICLES]


@pytest.mark.parametrize("path", PAGES)
def test_public_pages_render_with_seo_basics(client, path):
    r = client.get(path)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert 10 <= len(title) <= 90
    assert re.search(r'<meta name="description" content="[^"]{50,}"', html)
    assert f'<link rel="canonical" href="https://radynta.com{path}">' in html
    assert len(re.findall(r"<h1[\s>]", html)) == 1
    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    types = {n["@type"] for n in data["@graph"]}
    assert "Organization" in types
    # never fabricate ratings/reviews in structured data
    assert "aggregateRating" not in html and '"Review"' not in html


def test_homepage_hero_copy(client):
    html = client.get("/").get_data(as_text=True)
    assert "Help Your Logistics Business Get Discovered in AI Search" in html
    assert "Request a Logistics Visibility Audit" in html and "Explore Our Services" in html
    assert "SAMPLE" in html  # sample report preview is labelled


def test_no_guarantee_language(client):
    for path in PAGES:
        text = client.get(path).get_data(as_text=True).lower()
        for bad in ("we guarantee", "guaranteed results", "guaranteed #1", "#1 on google", "testimonial", "100% guarantee"):
            assert bad not in text, (path, bad)


def test_industry_pages_are_distinct(client):
    bodies = [re.sub(r"<[^>]+>", " ", client.get(f"/industries/{s}/").get_data(as_text=True)) for s in INDUSTRIES]
    intros = [INDUSTRIES[s]["intro"] for s in INDUSTRIES]
    for i, body in enumerate(bodies):
        for j, intro in enumerate(intros):
            assert (intro in body) == (i == j)


def test_sitemap_and_robots(client):
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    for p in PAGES:
        assert f"<loc>https://radynta.com{p}</loc>" in xml
    assert "/monitor" not in xml
    robots = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /monitor/" in robots and "Sitemap: https://radynta.com/sitemap.xml" in robots


@pytest.mark.parametrize("host", ["radynta.in", "www.radynta.in", "www.radynta.com"])
def test_secondary_hosts_redirect_to_canonical_preserving_path_and_query(client, host):
    r = client.get("/services/technical-seo/?utm_source=x&a=1", headers={"Host": host})
    assert r.status_code == 301
    assert r.headers["Location"] == "https://radynta.com/services/technical-seo/?utm_source=x&a=1"


def test_security_headers(client):
    r = client.get("/")
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_404(client):
    r = client.get("/no-such-page/")
    assert r.status_code == 404 and "noindex" in r.get_data(as_text=True)


# ------------------------------------------------------------ forms ---

def _audit_form(client, app, **overrides):
    page = client.get("/audit-request/").get_data(as_text=True)
    data = {"csrf_token": csrf_from(page), "form_ts": old_timer(app), "name": "Asha Patil", "email": "asha@konkan.example",
            "phone": "", "company": "Konkan Roadlines", "website": "konkan.example", "segment": "transport",
            "geography": "Maharashtra", "objective": "more_enquiries", "message": "", "consent": "yes"}
    data.update(overrides)
    return client.post("/audit-request/", data=data)


def test_valid_audit_request_is_stored(client, app, conn):
    r = _audit_form(client, app)
    assert r.status_code == 302 and "/thanks/audit/" in r.headers["Location"]
    row = conn.execute("SELECT * FROM enquiries").fetchone()
    assert row["company"] == "Konkan Roadlines" and row["consent"] == 1 and row["notified"] == 0
    thanks = client.get("/thanks/audit/").get_data(as_text=True)
    assert "don’t send automatic confirmation emails" in thanks  # no false claim of email sent


def test_validation_errors_shown_and_nothing_stored(client, app, conn):
    r = _audit_form(client, app, email="", phone="", consent="", segment="bogus", website="not a url")
    html = r.get_data(as_text=True)
    assert r.status_code == 400
    for msg in ("business email or a phone number", "consent", "logistics segment", "website address"):
        assert msg in html
    assert conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0] == 0


def test_missing_csrf_rejected(client, app, conn):
    r = client.post("/audit-request/", data={"name": "x", "form_ts": old_timer(app)})
    assert r.status_code == 400
    assert conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0] == 0


def test_honeypot_and_too_fast_submissions_not_stored(client, app, conn):
    assert _audit_form(client, app, company_website="http://spam.example").status_code == 302
    page = client.get("/audit-request/").get_data(as_text=True)
    r = _audit_form(client, app, form_ts=re.search(r'name="form_ts" value="([^"]+)"', page).group(1))  # just issued => too fast
    assert r.status_code == 302
    assert conn.execute("SELECT COUNT(*) FROM enquiries").fetchone()[0] == 0


def test_rate_limit(client, app):
    codes = [_audit_form(client, app).status_code for _ in range(6)]
    assert codes[:5] == [302] * 5 and codes[5] == 429


def test_contact_form(client, app, conn):
    page = client.get("/contact/").get_data(as_text=True)
    r = client.post("/contact/", data={"csrf_token": csrf_from(page), "form_ts": old_timer(app), "name": "Ravi",
                                       "email": "ravi@example.com", "message": "Do you work with 3PLs in Chennai?", "consent": "yes"})
    assert r.status_code == 302
    assert conn.execute("SELECT kind FROM enquiries").fetchone()["kind"] == "contact"
